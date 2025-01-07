import os
from openai import OpenAI 
import yaml
import re
import sys
from pathlib import Path
import unicodedata
import time

# Ensure you have set your OpenAI API key as an environment variable
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "<your OpenAI API key if not set as an env var>"))

# Get command line arguments
if len(sys.argv) != 5:
    print("Usage: python script.py <source_dir> <source_language> <destination_language> <destination_language_short_code>")
    sys.exit(1)

SOURCE_DIR = Path(sys.argv[1])
SOURCE_LANGUAGE = sys.argv[2]
DESTINATION_LANGUAGE = sys.argv[3]
DESTINATION_LANGUAGE_CODE = sys.argv[4]

DEST_DIR = SOURCE_DIR / DESTINATION_LANGUAGE_CODE

# Directories to process
DIRECTORIES = ['pages', '_posts', 'blog']

def generate_slug(title):
    # Convert title to lowercase, remove accents, replace spaces with hyphens
    title = title.lower()
    # Remove accents
    title = ''.join((c for c in unicodedata.normalize('NFD', title) if unicodedata.category(c) != 'Mn'))
    # Replace spaces and special characters with hyphens
    title = re.sub(r'[^a-z0-9]+', '-', title)
    # Strip leading/trailing hyphens
    title = title.strip('-')
    return title

def translate_text(text, source_language, target_language):
    # Use OpenAI API to translate text from source_language to target_language
    prompt = f"Translate the following text from {source_language} to {target_language}:\n\n{text}"
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"You are a helpful assistant that translates {source_language} to {target_language}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )
        translation = response.choices[0].message.content.strip()
        return translation
    except Exception as e:
        print(f"Error during translation: {e}")
        return text  # Return original text in case of error

def translate_markdown(markdown_text, source_language, target_language):
    # Use OpenAI API to translate Markdown content while preserving formatting
    prompt = f"Translate the following Markdown content from {source_language} to {target_language}, preserving the Markdown formatting, code blocks, links, and images:\n\n{markdown_text}"
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"You are a helpful assistant that translates {source_language} Markdown content to {target_language}, preserving the Markdown formatting, code blocks, links, and images."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )
        translation = response.choices[0].message.content.strip()
        return translation
    except Exception as e:
        print(f"Error during translation: {e}")
        return markdown_text  # Return original text in case of error

def translate_front_matter(front_matter_data, source_language, target_language):
    # Fields to translate
    fields_to_translate = ['title', 'subheadline', 'teaser']

    for field in fields_to_translate:
        if field in front_matter_data:
            front_matter_data[field] = translate_text(front_matter_data[field], source_language, target_language)

    # Translate categories and tags
    for field in ['categories', 'tags']:
        if field in front_matter_data:
            if isinstance(front_matter_data[field], list):
                translated_list = [translate_text(item, source_language, target_language) for item in front_matter_data[field]]
                front_matter_data[field] = translated_list
            else:
                front_matter_data[field] = translate_text(front_matter_data[field], source_language, target_language)

    # Update slug
    if 'title' in front_matter_data:
        translated_slug = generate_slug(front_matter_data['title'])
        front_matter_data['slug'] = translated_slug

    # Update permalink to include destination language code
    if 'permalink' in front_matter_data:
        permalink = front_matter_data['permalink']
        if not permalink.startswith(f'/{DESTINATION_LANGUAGE_CODE}/'):
            front_matter_data['permalink'] = f'/{DESTINATION_LANGUAGE_CODE}{permalink}'

    return front_matter_data

def translate_file(source_file, dest_file, source_language, target_language):
    # Read source file
    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split front matter and body
    match = re.match(r'---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if match:
        front_matter = match.group(1)
        body = match.group(2)
    else:
        print(f"No front matter found in {source_file}, skipping file.")
        return

    # Parse front matter
    front_matter_data = yaml.safe_load(front_matter)

    # Translate front matter fields
    front_matter_data = translate_front_matter(front_matter_data, source_language, target_language)

    # Translate body
    translated_body = translate_markdown(body, source_language, target_language)

    # Reconstruct content
    new_front_matter = yaml.dump(front_matter_data, allow_unicode=True, sort_keys=False)
    new_content = f"---\n{new_front_matter}---\n{translated_body}"

    # Ensure destination directory exists
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    # Write translated content to destination file
    with open(dest_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Translated file saved to {dest_file}")

def process_directory(directory, source_language, target_language):
    source_path = SOURCE_DIR / directory
    for root, dirs, files in os.walk(source_path):
        for file in files:
            if file.endswith('.md'):
                source_file = Path(root) / file
                # Determine destination file path
                relative_path = source_file.relative_to(SOURCE_DIR)
                dest_file = DEST_DIR / relative_path
                if dest_file.exists():
                    print(f"Destination file already exists: {dest_file}, skipping.")
                    continue
                else:
                    print(f"Translating file: {source_file}")
                    translate_file(source_file, dest_file, source_language, target_language)
                    # Sleep to respect API rate limits
                    time.sleep(1.1)  # Slightly longer sleep to ensure compliance

def main():
    for directory in DIRECTORIES:
        process_directory(directory, SOURCE_LANGUAGE, DESTINATION_LANGUAGE)

if __name__ == '__main__':
    main()
