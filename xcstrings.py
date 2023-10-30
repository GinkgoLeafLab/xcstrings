import os
import json
import datetime
import time

# pip install --upgrade googletrans==4.0.0rc1
from googletrans import Translator

# Global variables
is_info_plist = False
LANGUAGE_IDENTIFIERS = ['en', 'zh-Hans', 'zh-Hant', 'es', 'pt-PT', 'ja', 'ko']
LANGUAGE_IDENTIFIERS_FOR_GOOGLE = {
    'zh-Hans': 'zh-CN', 
    'zh-Hant': 'zh-TW',
    'zh-HK': 'zh-TW',
    'pt-PT': 'pt'
}

# Use automatic detection source language for translation
def translate_string(string, target_language):
    translator = Translator()
    
    if target_language not in LANGUAGE_IDENTIFIERS_FOR_GOOGLE:
        dest = target_language
    else:
        dest = LANGUAGE_IDENTIFIERS_FOR_GOOGLE[target_language]

    try:
        source_language = translator.detect(string).lang
        if source_language == dest:
            return string
        
        translation = translator.translate(string, dest=dest)
    except Exception as e:
        print(e)
        print("Translation timeout, retrying after 1 seconds...")
        time.sleep(1)
        return translate_string(string, target_language)
        
    print(f"{target_language}: {translation.text}")
    return translation.text

def main():
    # Get all the keys of strings
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    strings_keys = list(json_data["strings"].keys())

    print(f"\nFound {len(strings_keys)} keys\n")

    # Traverse all keys
    for key_index, key in enumerate(strings_keys):
        if not key:
            continue
        # Get the current time
        now = datetime.datetime.now()
        # Format the current time
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now_str}]\n", f"🔥{key_index + 1}/{len(strings_keys)}: {key}")

        strings = json_data["strings"][key]

        # The strings field is empty.
        if not strings:
            strings = {"extractionState": "manual", "localizations": {}}
        
        # The localizations field is empty
        if "localizations" not in strings:
            strings["localizations"] = {}
    
        localizations = strings["localizations"]

        for language in LANGUAGE_IDENTIFIERS:
            # Determine whether localizations contains the corresponding language key
            if language not in localizations:
                if not is_info_plist:
                    # If not included, use Googletrans to fill in "localizations" after translation.
                    source_string = (
                        localizations["en"]["stringUnit"]["value"]
                        if "en" in localizations
                        else key
                    )
                    localizations[language] = {
                        "stringUnit": {
                            "state": "translated",
                            "value": translate_string(source_string, language),
                        }
                    }
                else:
                    source_language = json_data["sourceLanguage"]
                    if source_language not in localizations:
                        print("String is empty in source language")
                        continue
                    else:
                        source_string = (
                            localizations["en"]["stringUnit"]["value"]
                            if "en" in localizations
                            else localizations[source_language]["stringUnit"]["value"]
                        )
                        localizations[language] = {
                            "stringUnit": {
                                "state": "translated",
                                "value": translate_string(source_string, language),
                            }
                        }
            else:
                print(f"{language} has been translated")

        strings["localizations"] = localizations
        json_data["strings"][key] = strings

        # Save the modified JSON file every time to prevent flashback.
        with open(json_path, "w", encoding='utf-8') as f:
            json.dump(json_data, ensure_ascii=False, fp=f, indent=4)

def is_infoplist(json_path):
    """
    Determine whether the file name is "InfoPlist.xcstrings" 
    
    Args: 
        json_path: File path 
    Returns: 
        True: Yes "InfoPlist.xcstrings" 
        False: Not "InfoPlist.xcstrings" 
    """

    filename = os.path.basename(json_path)
    return filename == 'InfoPlist.xcstrings'

if __name__ == "__main__":
    # Input json_path from terminal
    json_path = input("Enter the string Catalog (.xcstrings) file path:\n")
    is_info_plist = is_infoplist(json_path)
    main()
