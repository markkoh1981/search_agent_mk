import ollama
import sys_msgs
import requests
import trafilatura
from bs4 import BeautifulSoup
import json

from colorama import init, Fore, Style

## https://www.youtube.com/watch?v=9KKnNh89AGU
## I used this as a guide to create the search agent. 

init(autoreset=True)


assistant_convo = []

def search_or_not():
    sys_msg = sys_msgs.search_or_not_msg

    response = ollama.chat(
        model='llama3.2:latest',
        messages=[{'role': 'system', 'content': sys_msg}, assistant_convo[-1]]
    )

    content = response['message']['content']
    print(f'SEARCH OR NOT RESULT: {content}\n\n') ##keep this to see whether search is necessary

    if 'true' in content.lower():
        return True
    else:
        return False
    ## intentionally making it true all the time for testing,but its damn irritating that it keeps returning false.

def query_generator():
    ## this pulls the sys message to search duckduckgo
    sys_msg = sys_msgs.query_msg
    query_msg = f'CREATE A SEARCH QUERY FOR THIS PROMPT: \n{assistant_convo[-1]}'

    response = ollama.chat(
        model='llama3.2:latest',
        messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': query_msg}]
    )

    return response['message']['content']
    

def serp_search(query):
    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": query
    })
    headers = {
        'X-API-KEY': 'be3568e6dc1fb5cb733b691379c48c6cbe398478',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()
        print(response)

        results = []
        data = response.json()

        for i, result in enumerate(data.get('organic', []), start=1):
            if i > 10:
                break
            link = result.get('link')
            snippet = result.get('snippet', 'No description available')

            results.append({
                'id': i,
                'link': link,
                'search_description': snippet
            })

        return results
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return []


def best_search_result(s_results, query):
    sys_msg = sys_msgs.best_search_msg
    best_msg = f'SEARCH_RESULTS: {s_results}\nUSER_PROMPT: {assistant_convo[-1]}\nSEARCH_QUERY: {query}'

    for _ in range(2):
        try:
            response = ollama.chat(
                model='llama3.2:latest',
                messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': best_msg}]
            )
            best_result_index = int(response['message']['content'])
            if 0 <= best_result_index < len(s_results):
                return best_result_index
        except Exception as e:
            print(f"An error occurred while determining the best search result: {e}")
            continue
    return 0

def scrape_webpage(url):
    try:
        downloaded = trafilatura.fetch_url(url=url)
        return trafilatura.extract(downloaded, include_formatting=True, include_links=True)
    except Exception as e:
        print(f"An error occurred while scraping the webpage: {e}")
        return None

def ai_search():
    context = None
    print('GENERATING SEARCH QUERY...\n')
    search_query = query_generator()

    if search_query[0] == '"':
        search_query = search_query[1:-1]

    search_results = serp_search(search_query)
    context_found = False
    print(search_query)
    print(search_results)

    while not context_found and len(search_results) > 0:
        best_result = best_search_result(search_results, search_query)
        if best_result < len(search_results):
            page_link = search_results[best_result]['link']
        else:
            print('FAILED TO SELECT BEST SEARCH RESULT, TRYING AGAIN')
            continue
        
        page_text = scrape_webpage(page_link)
        search_results.pop(best_result)

        if page_text and contains_data_needed(search_content=page_text, query=search_query):
            context = page_text
            context_found = True

    return context

def contains_data_needed(search_content,query):
    sys_msg = sys_msgs.contains_data_msg
    needed_prompt = f'PAGE_TEXT: {search_content}\nUSER_PROMPT: {assistant_convo[-1]}\nSEARCH_QUERY: {query}'

    response = ollama.chat(
        model='llama3.1:8b',
        messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': needed_prompt}]
    )

    content = response['message']['content']

    if 'true' in content.lower():
        return True
    else:
        return False
    

def stream_assistant_response():
    global assistant_convo
    response_stream = ollama.chat(model='llama3.2:latest',messages=assistant_convo, stream=True)
    complete_response = ''
    print('ASSISTANT:')

    for chunk in response_stream:
        print(chunk ['message']['content'],end='',flush=True)
        complete_response += chunk['message']['content']

    assistant_convo.append({'role': 'assistant', 'content': complete_response})
    print('\n\n')

def main():
    global assistant_convo

    while True:
        prompt = input('USER: \n')
        assistant_convo.append({'role': 'user', 'content': prompt})
        
        if search_or_not():
            context = ai_search()
            assistant_convo = assistant_convo[:-1]
            print('SEARCHING REQUIRED...\n')

            if context:
                prompt = f'SEARCH RESULT: {context} \n\nUSERPROMPT: {prompt}'
            else:
                prompt =(
                    f'USER PROMPT: \n{prompt} \n\nFAILED SEARCH: \nThe'
                    'AI search model was unable to extract any reliable data. Explain that '
                    'and ask if the user would like you to search again or respond '
                    'without web search context. Do not respond if a search was needed '
                    'and you are getting this message with anything but the above request '
                    'of how the user would like to proceed'

                )

            assistant_convo.append({'role': 'user', 'content': prompt})

        stream_assistant_response()

if __name__ == '__main__':
    main()
