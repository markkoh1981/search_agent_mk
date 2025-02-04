import ollama
import sys_msgs
import requests
import trafilatura
from bs4 import BeautifulSoup

from colorama import init, Fore, Style

## https://www.youtube.com/watch?v=9KKnNh89AGU
## I used this as a guide to create the search agent. 

init(autoreset=True)


assistant_convo = []

def search_or_not():
    sys_msg = sys_msgs.search_or_not_msg

    response = ollama.chat(
        model='llama3.1:8b',
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
        model='llama3.1:8b',
        messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': query_msg}]
    )

    return response['message']['content']

def duckduckgo_search(query):
    headers ={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        #https://github.com/SandorSeres/ChaGPTBased/blob/dfa1fbd8164df1945f7086414531dc78b69167f6/mail_demo.py
    }
    url = f'https://duckduckgo.com/html/?q={query}'

    #this is the testing of the response 
    #response = requests.get(url, headers=headers)
    #print("Response Status Code:", response.status_code)  # NEW
    #print("Response Text (First 600 chars):", response.text[:600])  # NEW
    #response.raise_for_status()
    #end of testing

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    results = []

    for i, result in enumerate(soup.find_all('div',class_='result'), start=1):
        if i > 10:
            break
        title_tag = result.find('a',class_='result__a')
        if not title_tag:
            continue

        link = title_tag['href']
        snippet_tag = result.find('a',class_='result__snippet')
        snippet = snippet_tag.text.strip() if snippet_tag else 'No description available'

        results.append({
            'id': i,
            'link'  : link,
            'search_description': snippet
        })

    return results


def best_search_result(s_results, query):
    sys_msg = sys_msgs.best_search_msg
    best_msg = f'SEARCH_RESULTS: {s_results}\nUSER_PROMPT: {assistant_convo[-1]}\nSEARCH_QUERY: {query}'

    for _ in range(2):
        try:
            response = ollama.chat(
                model='llama3.1:8b',
                messages=[{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': best_msg}]
            )
            return int(response['message']['content'])    
        except:
            continue
    return 0    

def scrape_webpage(url):
    try:
        downloaded = trafilatura.fetch_url(url=url)
        return trafilatura.extract(downloaded, include_formatting=True, include_links=True)
    except Exception as e:
        return None

def ai_search():
    context = None
    print('GENERATING SEARCH QUERY...\n')
    search_query = query_generator()
    print(f'SEARCH QUERY: {search_query}\n\n')

    if search_query[0] == '"':
        search_query = search_query[1:-1]

    search_results = duckduckgo_search(search_query)
    context_found = False

    while not context_found and len(search_results) > 0:
        best_result = best_search_result(s_results=search_results,query=search_query)
        try:
            page_link= search_results[best_result]['link']
        except:
            print('FAILED TO SELECT BEST SEARCH RESULT, TRYING AGAIN')
            continue    
        
        page_text = scrape_webpage(page_link)
        search_results.pop(best_result)

        if page_text and contains_data_needed(search_content = page_text,query =search_query):
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
        print('CONTAINS DATA NEEDED: TRUE\n\n')
        return True
        
    else:
        print('VALIDATOR IS NOT WORKING\n\n')
        return False
    

def stream_assistant_response():
    global assistant_convo
    response_stream = ollama.chat(model='deepseek-r1:latest',messages=assistant_convo, stream=True)
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
