import os
import json
import datetime
import time
import threading
import re
from collections import defaultdict
import requests
import random
import sys

# Global configuration variables
GOOGLE_API_KEY = ''
APPCATEGORY = ""
LANGUAGE_IDENTIFIERS = ['zh-Hans', 'zh-Hant']
BATCH_SIZE = 4000
SEPARATOR = "||"
# Global variable for untranslated state
add_extraction_state = False

# Global variables
is_info_plist = False

def exponential_backoff(retry_count, base_delay=1, max_delay=60):
    exponential_delay = min(base_delay * (2 ** retry_count), max_delay)
    actual_delay = exponential_delay + random.uniform(0, 1)  # Add jitter
    return actual_delay

def print_elapsed_time(start_time, stop_event):
    while not stop_event.is_set():
        elapsed_time = time.time() - start_time
        print(f"Elapsed time: {elapsed_time:.2f} seconds")
        time.sleep(1)

# Use automatic detection source language for translation
def translate_batch(strings, target_language):
    time.sleep(1)
    prompt = f"""You are a professional localization service provider specializing in translating content for specific languages, cultures, and categories.
    For example:
    <Start>
    Hello{SEPARATOR}World{SEPARATOR}谷歌
    <End>
    The translation is:
    <Start>
    你好{SEPARATOR}世界{SEPARATOR}谷歌
    <End>
    
    Translate the following content to {target_language} Language"""
    
    if APPCATEGORY:
        prompt += f" for the app categorized as a {APPCATEGORY}."
        
    prompt += f"""
    Each item is separated by {SEPARATOR}. Please keep the same structure (Keep the structure such as line breaks) in your response.

    <Start>{SEPARATOR.join(strings)}<End>"""
    
    headers = {
        'Content-Type': 'application/json',
    }

    params = {
        'key': GOOGLE_API_KEY,
    }

    json_data = {
        'contents': [
            {
                'parts': [
                    {
                        'text': prompt,
                    },
                ],
            },
        ],
    }

    retry_count = 0
    while True:
        try:
            start_time = time.time()
            stop_event = threading.Event()
            timer_thread = threading.Thread(target=print_elapsed_time, args=(start_time, stop_event))
            timer_thread.start()
            print("Starting translation request...")
            response = requests.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent', 
                                     params=params, headers=headers, json=json_data)
            stop_event.set()
            timer_thread.join()
            response.raise_for_status()
            print("Request successful!")
            data_parsed = response.json()
            print("Response data:", data_parsed)
            result = get_text_from_json(data_parsed)
            match = re.search('<Start>(.*?)<End>', result, re.DOTALL)
            if match:
                translated_text = match.group(1).strip()
                return translated_text.split(SEPARATOR)
            else:
                continue
        except Exception as e:
            stop_event.set()
            timer_thread.join()
            print(f'{type(e).__name__}: {e}')
            retry_count += 1
            delay = exponential_backoff(retry_count)
            print(f"Translation timeout, retrying after {delay:.2f} seconds...")
            time.sleep(delay)

# Function to safely get the 'text' from parsed JSON data
def get_text_from_json(data):
    try:
        # Ensure 'candidates' is a list and not empty
        if (isinstance(data.get('candidates'), list) and
                len(data['candidates']) > 0):
            
            content = data['candidates'][0].get('content')
            # Ensure 'content' has a 'parts' list and it's not empty
            if content and isinstance(content.get('parts'), list) and len(content['parts']) > 0:
                
                text = content['parts'][0].get('text')
                # Return text if it's a string, otherwise, return a default string or raise an error
                return text if isinstance(text, str) else 'No text found'
        # If checks fail, return a default value or raise an error
        return 'No text found'
    except Exception as e:
        print(f'Error retrieving text: {e}')
        # Handle the exception as needed (e.g., return a default value, raise an error, log the issue, etc.)
        return 'No text found'

def process_others_translations(json_data, language, keys, strings_to_translate_list):
    translated_strings = translate_batch(strings_to_translate_list, language)
    for key, translated in zip(keys, translated_strings):
        print(f"{language}: {key} ==> {translated}")
        json_data["strings"][key]["localizations"][language] = {
            "stringUnit": {
                "state": "translated",
                "value": translated,
            }
        }

def clear():
    # for windows
    if os.name == 'nt':
        _ = os.system('cls')
    # for mac and linux(here, os.name is 'posix')
    else:
        _ = os.system('clear')

def main():
    try:
        # Get all keys of strings from file path provided in config
        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"Error decoding JSON data: {e}")
        return

    # Clearing the Screen
    clear()
    
    if not APPCATEGORY:
        print(f"Begin the localization process at path:\n{json_path}")
    else:
        print(f"Begin the localization process for the app categorized as a {APPCATEGORY} at path:\n{json_path}")

    # Use LANGUAGE_IDENTIFIERS from config (skip interactive prompt)

    strings_to_translate = {}
    source_language = json_data["sourceLanguage"]

    # Removed interactive untranslated state prompt; using global add_extraction_state from config
    # mark_untranslated_manual input has been replaced by config value in __main__

    for key, strings in json_data["strings"].items():
        if "comment" in strings and "ignore xcstrings" in strings["comment"] or \
           ("shouldTranslate" in strings and strings["shouldTranslate"] == False):
            continue
        if not strings:
            if add_extraction_state:
                strings = {"extractionState": "manual", "localizations": {}}
            else:
                strings = {"localizations": {}}
        if "localizations" not in strings:
            strings["localizations"] = {}
        json_data["strings"][key] = strings
        localizations = strings["localizations"]
        source_string = localizations[source_language]["stringUnit"]["value"] if source_language in localizations else key
        
        for language in LANGUAGE_IDENTIFIERS:
            if language not in localizations or localizations[language]["stringUnit"]["state"] != "translated":
                strings_to_translate[(language, key)] = source_string
            else:
                print(f"{language}: {{{key}: {source_string}}} has been translated")

    # Process any remaining strings for each language
    if strings_to_translate:
        languages = set(lang for lang, _ in strings_to_translate.keys())
        for language in languages:
            lang_strings = {key: value for (lang, key), value in strings_to_translate.items() if lang == language}
            if not lang_strings:
                continue
            
            keys = list(lang_strings.keys())
            strings_to_translate_list = list(lang_strings.values())
            # Loop through the strings in chunks
            start_index = 0
            while start_index < len(strings_to_translate_list):
            # Determine the end index for the current chunk
                combined_string = ""
                end_index = start_index
                while end_index < len(strings_to_translate_list) and len(combined_string + strings_to_translate_list[end_index] + SEPARATOR) <= BATCH_SIZE:
                    combined_string += strings_to_translate_list[end_index] + SEPARATOR
                    end_index += 1
                
                # Remove the trailing separator
                combined_string = combined_string.rstrip(SEPARATOR)
                # Process the current chunk of translations
                process_others_translations(json_data, language, keys[start_index:end_index], strings_to_translate_list[start_index:end_index])
                # Update the start index for the next chunk
                start_index = end_index

    # Save the modified JSON file
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(json_data, ensure_ascii=False, fp=f, indent=4)

if __name__ == "__main__":
    # Expect a config file path as the first CLI argument
    if len(sys.argv) < 2:
        print("Usage: python xcstrings_Gemini.py <config_file_path>")
        sys.exit(1)
    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = {}
            for line in config_file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    except Exception as e:
        print(f"Error reading config file: {e}")
        sys.exit(1)
    
    # Set global variables from config
    GOOGLE_API_KEY = config.get("gemini_api_key", "")
    if not GOOGLE_API_KEY:
        raise ValueError("gemini_api_key not provided in the config file.")
    APPCATEGORY = config.get("app_category", "")
    LANGUAGE_IDENTIFIERS = [lang.strip() for lang in config.get("language_codes", "en,zh-Hans,zh-Hant").split(",")]
    json_path = config.get("xcstrings_file_path", "")
    if not json_path:
        raise ValueError("xcstrings_file_path not provided in the config file.")
    if config.get("untranslated_state", "0").strip() == "1":
        add_extraction_state = True
    else:
        add_extraction_state = False

    if os.path.exists(json_path):
        print(f"File found at: {json_path}")
        main()
    else:
        print(f"Error: No such file or directory: '{json_path}'")
