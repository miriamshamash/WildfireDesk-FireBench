from build.lib.llmproxy import LLMProxy
import time
import datetime
import sys
from os import walk
from string import Template
from pathlib import Path
import requests
import json
from operator import itemgetter
import ast
from bs4 import BeautifulSoup
from urllib.parse import urlparse

### ----------------------------------------------------------------------------------------------------
### System Settings      -
### ----------------------------------------------------------------------------------------------------

timestamp_format = "%Y-%m-%d_%H-%M-%S"
timestamp = datetime.datetime.now().strftime(timestamp_format)
timestamp_stale_allowance = 1
crawl_depth = 1
SUMMARIZE = 0
SEARCH = 1
verbose = True
display_rag = 0
chatbot_democracy_resources_directory = "sage-resources/democracy-chatbot-resources"
chatbot_wildfire_resources_directory = "sage-resources/wildfire-resources"
sage_instructions_directory = "sage-resources/sage-instructions"
upload_resources = False
crawl_time = ""
news_resources = "sage-resources/web-crawl-data"
news_region_resources = "sage-resources/state-local-news-outlets"
selected_state = "California"
selected_community = "Bay Area"
conduct_internet_search = True

# I want to make a social group that tartet problemt black voters care about, what shoudl I put in my mission statement to be relevant?

### ----------------------------------------------------------------------------------------------------
### Sage Settings        -
### ----------------------------------------------------------------------------------------------------

sage = LLMProxy()
sage_tone = ""
sage_interaction = ""
sage_formatting = ""
sage_drafting = ""
sage_guardrails = ""
sage_intro = ""
sage_privacy = ""
sage_model = '4o-mini' # subject to change
sage_temperature = 0.6 # subject to change
sage_session_id = "sage"+str(timestamp) # subject to change --> may need to save
sage_RAG_id = "sage_rag2"#+str(timestamp)
sage_rag_t = 0.4 # subject to change
sage_rag_k = 5 # top number of chunks to fetch to use for rag, lets see if we need to set this

### ----------------------------------------------------------------------------------------------------
### Ivy Settings        -
### ----------------------------------------------------------------------------------------------------
# I propose our web crawler be named Ivy! This is a crawling and climbing vine that (unfortunately) can spread
# fires, especially in california


ivy = LLMProxy()
ivy_model = 'gemini-2.5-flash-lite'
# ivy_html_system = f"""You will receive the raw HTML of a webpage. Extract the key findings, important topics, and any key dates. Respond briefly and clearly."""
ivy_html_system = f"""You will receive the raw HTML of a webpage and user input in the format HTML:<HTML> UserInput:<usr>. Extract the key findings from the webpage that is related to the user input. Respond briefly and clearly."""
# ivy_discern_system = f"""You will receive a question, first answer with either 'Yes' or 'No'. Then respond with a reason in the format: Why: <reason>."""
ivy_discern_system = f"""respond in the format: <Yes or No>|<reason why>"""
ivy_url_disection = f"""You will recieve a list of links from a webpage and a user input in the format URLs:<URL list> UserInput:<usr>. Return all urls that would lead to a news article in the format: [<url>, <url>, ... <url>]. For example: [\"https://foo\", \"https://bar\"]. If there are no urls present respond with: []"""
ivy_session_id = "ivy"+str(timestamp)
ivy_temperature = 0.2 # subject to change


### ----------------------------------------------------------------------------------------------------
### Helpers        -
### ----------------------------------------------------------------------------------------------------

def load_text_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Error: could not find file {filepath}")
        return None
    except PermissionError:
        print(f"Error: permission denied when opening file {filepath}")
        return None
    except OSError as e:
        print(f"Error: could not open file {filepath}: {e}")
        return None


def build_sage_system_prompt():
    return "\n\n".join([
        sage_tone,
        sage_interaction,
        sage_formatting,
        sage_drafting,
        sage_guardrails,
        sage_privacy
    ])


def rag_context_string_simple(rag_context):
    """
    Convert the RAG context list (from retrieve API)
    into a single plain-text string that can be appended to a query.
    """
    context_string = ""
    i=1
    for collection in rag_context:
        if not context_string:
            context_string = """The following is additional context that may be helpful in answering the user's query."""

        context_string += """
        #{} {}
        """.format(i, collection['doc_summary'])
        j=1
        for chunk in collection['chunks']:
            context_string+= """
            #{}.{} {}
            """.format(i,j, chunk)
            j+=1
        i+=1
    return context_string


def parse_retrieve_rag_context(rag_ctx):
    # the rag cotext from retrieve() is a list of dictionaries with the keys: doc_id, doc_summary and chunks.
    summaries = ""
    index = 1
    for rec in rag_ctx:
        summaries += f"""{str(index)}. {rec["doc_summary"]}\n"""
        index+=1
    
    return summaries, index

### ----------------------------------------------------------------------------------------------------
### Sage Setup        -
### ----------------------------------------------------------------------------------------------------

def upload_to_sage(filepath):
    response = sage.upload_file(
        file_path = filepath,
        session_id = sage_RAG_id,
        strategy = 'smart' 
    )
    time.sleep(3)
    if "result" not in response:
        print("Resource upload error\n")
        print("Full response:", response)
        return False
    resp_message = response["result"]
    if verbose and display_rag > 0:
        fileparts = str(filepath).split("/")
        name = fileparts[len(fileparts) - 1]
        print("Upload Status: " + resp_message + ", Filename: " + name)
    elif verbose:
        print("Upload Status: " + resp_message)
    return resp_message == "success"


def upload_2d_directory(filepath_str):
    p = Path(filepath_str)
    for data in p.iterdir():
        if data.is_dir():
            for file in data.iterdir():
                # print("Name: ", file.name, "Relative: ", file.relative_to("."), "\n")
                if not upload_to_sage(file.relative_to(".")):
                    print(f"""File: {file.name} - failed to upload\n""")
                    return False
        elif data.is_file():
            if not upload_to_sage(data.relative_to(".")):
                    print(f"""File: {data.name} - failed to upload\n""")
                    return False
    return True


def setup_sage():
    global sage_tone
    global sage_interaction
    global sage_formatting
    global sage_drafting
    global sage_guardrails
    global sage_intro
    global sage_privacy

    if upload_resources:
        if not upload_2d_directory(chatbot_democracy_resources_directory):
            return False
        if not upload_2d_directory(chatbot_wildfire_resources_directory):
            return False
    try:
        sage_tone = load_text_file(f"{sage_instructions_directory}/sage-tone.txt")
        sage_interaction = load_text_file(f"{sage_instructions_directory}/sage-interaction.txt")
        sage_formatting = load_text_file(f"{sage_instructions_directory}/sage-formatting.txt")
        sage_drafting = load_text_file(f"{sage_instructions_directory}/sage-drafting.txt")
        sage_guardrails = load_text_file(f"{sage_instructions_directory}/sage-guardrails.txt")
        sage_intro = load_text_file(f"{sage_instructions_directory}/sage-introduction.txt")
        sage_privacy = load_text_file(f"{sage_instructions_directory}/sage-privacy.txt")
    except:
        return False

    if (
        sage_tone is None or
        sage_interaction is None or
        sage_formatting is None or
        sage_drafting is None or
        sage_guardrails is None or
        sage_intro is None or
        sage_privacy is None
    ):
        print("One of more of sage's instructions failed to load.")
        return False

    return True

### ----------------------------------------------------------------------------------------------------
# Core Chat Logic
### ----------------------------------------------------------------------------------------------------

def prompt_sage(query_prompt, include_rag=True):
    final_query = ""
    rag_context = []

    if include_rag:
        rag_context = sage.retrieve(
            query = query_prompt,
            session_id = sage_RAG_id,
            rag_threshold=sage_rag_t,
            rag_k=sage_rag_k
        )

        final_query = Template("$query\n$rag_context").substitute(
                                query=query_prompt,
                                rag_context=rag_context_string_simple(rag_context))
    else:
        final_query = query_prompt

    full_system_prompt = build_sage_system_prompt()

    response = sage.generate(
        model = sage_model,
        system = full_system_prompt,
        query = final_query,
        temperature = sage_temperature,
        session_id = sage_session_id,
        lastk=3, # the citation proccess usually take three prompts, unsure if this is helpful
    )

    return response, rag_context

def get_intro():
    response, _ = prompt_sage(sage_intro, include_rag=False)
    return response["result"]

def get_source(rag_context):
    # Here is an example of that format:
    # 1. **"Ella Taught Me: Shattering the Myth of the Leaderless Movement" - Colorlines**
    # - This document addresses the misconception of leaderless movements, emphasizing the importance of organized leadership and collective strategy within social movements. It references historical examples such as the Student Nonviolent Coordinating Committee (SNCC) and the Black Panther Party, highlighting the concept of group-centered leadership as essential for accountability and effective mobilization.
    # - Key Sections:
    #     - **Group-Centered Leadership**: Discusses the necessity for structured organizations like the Black Youth Project 100 (BYP100) and their approach to activism.
    #     - **Collective Strategy**: Emphasizes the need for organizations to ensure accountability and coordinated efforts among activists.
    #     - **Experiences in Movements**: Reflects on the author's experiences balancing mobilization with organization-building and the importance of communication.
    source_prompt = f"""What documents are referenced in the doc_summary sections of this Rag Context?<start> {rag_context} <end>
    
    If there is only empty space between <start> and <end> reply with three empty spaces.

    Otherwise, make sure your answer follows the format: **[Document Name]**\n - [Summary]\n - [Key sections referenced]
    """
    
    # response, _ = prompt_sage(source_prompt) # Commented out and seems to be fixing the double citation problem, but tbh who knows

    doc_summaries = parse_retrieve_rag_context(rag_context)

    citation_prompt = f"""
        You are generating a short "Where this advice comes from" section for a user.

        Documents:
        {doc_summaries}

        Write the output in TWO parts:

        PART 1 — SUMMARY PARAGRAPH
        Write a short paragraph (2–3 sentences total) that:
        - explains what kinds of sources this advice draws from
        - describes the perspective or approach these sources take
        - clearly connects that perspective to the advice given

        Rules for the paragraph:
        - Use plain, non-academic language
        - Do not use markdown of any kind
        - Do not use bold, italics, or symbols such as ** or *
        - Do not use headings
        - Write in clean plain text only

        PART 2 — CITATIONS
        Under the paragraph, provide MLA-style citations for the same sources.

        Rules for citations:
        - Use a simple numbered list (1., 2., 3.)
        - Each citation must be a single line of plain text
        - Include only information that is available (author, title, date, publisher, link)
        - Do not guess or fabricate missing information
        - Do not use placeholders such as "[No date available]"
        - Do not use markdown
        - Do not use bold, italics, or symbols such as ** or *
        - Do not use headings
        - Do not include extra explanation

        FINAL OUTPUT RULES:
        - Return only plain text
        - Do not include section titles or labels
        - Do not include "MLA-style citations" or any header
        - Do not include markdown anywhere in the output
        """
    
    response, _ = prompt_sage(citation_prompt)
    return response["result"]
    
def chat_with_sage(user_message):
    web_results = []
    if conduct_internet_search:
        web_results = search_web(user_message, selected_state, selected_community)

    # TODO: format the web results in a way we can pass them to Sage so that she has that context when generating her answer

    response, rag_context = prompt_sage(user_message)
    answer = response["result"]

    sources = None
    if len(rag_context) > 0:
        sources = get_source(rag_context)
    else:
        warning = (
            "Note: This answer is based on general knowledge and may not reflect "
            "specific local policies or up-to-date recovery information. "
            "You may want to verify details with local agencies."
        )
        answer = f"{answer}\n\n---\n{warning}"


    return {
        "answer": answer,
        "sources": sources,
        "used_rag": len(rag_context) > 0,
        "rag_context": rag_context,
        "web_results": web_results
    }

def add_summary(state, move_ahead=0):
    input_file = f"""sage-resources/state-local-news-outlets/{state}.jsonl"""
    output_file = f"""sage-resources/state-local-news-summaries/{state}.jsonl"""
    retry = 2
    failed = []

    with open(input_file, "r", encoding="utf-8") as infile, \
     open(output_file, "a", encoding="utf-8") as outfile:
        skip = 0


        for line in infile:
            if skip != move_ahead:
                skip += 1
                print("Skip: ", skip)
                continue
            record = json.loads(line)
            url = record["Website"]
            local_retry = retry
            success = False
            if "http" in url:
                while local_retry != 0:
                    try:
                        page = requests.get(url)
                        # Add summary field
                        html_content = extract_html_content(page.text)
                        # ivy_prompt = f"""HTML:{html_content} UserInput: Summarize the content of this webpage in 4 sentences. Mention the main topic, key words and any social groups of people it mentions. Then determine if it is True or False that you were able to make a meaningful summary of the webpage.
                        # Return your response in the format: <Summary>|<True or False>"""

                        ivy_prompt = f"""HTML:{html_content} UserInput: Summarize the content of this webpage in 4 sentences. Mention the main topic, key words and any social groups of people it mentions."""

                        resp = prompt_ivy(ivy_prompt, ivy_html_system)
                        record["Summary"] = extract_response_string(resp)

                        print(record)
                        # Write updated record
                        outfile.write(json.dumps(record) + "\n")
                        success = True
                        break
                    except:
                        # just give up on this one and continue
                        local_retry -= 1
                        print("Retry: ", local_retry)
                if not success:
                    failed.append(record)
    
    print("All failed records: \n", failed)

def get_all_supported_states():
    states = []
    # _, _, state_files = 
    for (_, _, filenames) in walk(news_region_resources):
        for file in filenames:
            fname = file.replace("_", " ")
            state_name = fname.split(".")[0]
            states.append(state_name)
        break
    return states

# The General community will encompass all new sites that have the community listed as - or --
def get_all_supported_communities(state):
    communitites = set()
    state_file = f"""{news_region_resources}/{state}.jsonl"""
    with open(state_file, "r", encoding="utf-8") as infile:
        for line in infile:
            record = json.loads(line)
            com = record["Community"]
            if com.count("-") != len(com):
                communitites.add(com)
            else:
                communitites.add("General")

    return list(communitites)

     
def search_web(usr, state, community):    
    discern_query = f"""The user said this: {usr}\nwould an response to the above benefit from information from local news coverage?"""

    discern_retry = 2
    while discern_retry != 0:
        resp = prompt_ivy(discern_query, ivy_discern_system)
        response_parts = extract_response_string(resp).split("|")
        log_ivy(resp)
        if len(response_parts) != 2:
            # Something has gone wrong with formatting, dont conduct internet search
            discern_retry -= 1
            continue
        elif response_parts[0] == "Yes":
            print("Local news was deemed useful")
            break
        elif response_parts[0] == "No":
            print("No internet search was deemed necessary")
            return []
        else:
            discern_retry -= 1
            continue
    if discern_retry == 0:
        print("Discernment failed")
        return []
    
    state_file = f"""{news_region_resources}/{state}.jsonl"""
    outlet_records = get_all_crawl_data(state_file, community)

    all_outlet_res = []
    for i in range(len(outlet_records)):
        outlet_rec = outlet_records[i]
        root_name = outlet_rec["Outlet"]
        root = get_root(root_name)
        print("Root: ", root)
        global crawl_time # TODO: re-eval whether or not this needds to be a global
        crawl_time = datetime.datetime.now().strftime(timestamp_format)
        news_records = []
        print("Outlet has been selected as relevant: ", root_name)
        if redo_crawl_check(root, crawl_time):
            print("We are gonna crawl: ", root_name)
            site_crawl(crawl_depth, outlet_rec["Website"], usr, news_records, SUMMARIZE)
            
            print("Final records length: ", len(news_records))
            print(f""" Records: {news_records}""")
            # Note below completely cleans the file any time its opened like this, if we want to keep
            # record we will need to implement extra logic
            crawl_file = open(f"""{news_resources}/{root_name}.jsonl""", "w")
            for r in news_records:
                crawl_file.write(json.dumps(r) + "\n")
            crawl_file.close()
        else:
            print("This site already has crawled relevant data stored: ", root_name)
            state_file = f"""{news_resources}/{root_name}.jsonl"""
            news_records = get_all_crawl_data(state_file)
        filename = f"""{news_resources}/{root_name}.jsonl"""
        sum = get_summaries_list(filename)
        if sum == "":
            print("Something went wrong with making the summary")
            return all_outlet_res
        eval_summaries_prompt = f"""Here is a numbered list of a summary of resources:\n{sum}
        For each summary determine whether it is True or False that a webpage with that content would be beneficial to providing a response to this user input: {usr}.
        Respond in this format: {{<number>:<True or False>, <number>:<True or False>, ..., <number>:<True or False>}}"""

        print(eval_summaries_prompt)

        retry = 2
        valid = False
        record_ledger = {}
        while retry > 0:
            resp = prompt_ivy(eval_summaries_prompt, ivy_html_system)
            log_ivy(resp)
            resp_str = extract_response_string(resp)
            try:
                record_ledger = ast.literal_eval(resp_str)
            except:
                retry -= 1
                continue
            valid = True
            break
        
        if not valid:
            print("There was a problem getting the ledger")
            return all_outlet_res

        # THis will aggregate the information based on what the usr asked and the content
        web_info = []
        for i in range(len(news_records)):
            try:
                if record_ledger[i + 1]:
                    print("Exploring record: ", i+1)
                    target = news_records[i]
                    site_crawl(0, target["URL"], usr, web_info, SEARCH)
                    if web_info[-1]["Summary"] != "None":
                        web_record = {
                            "Timestamp": web_info[-1]["Timestamp"],
                            "Outlet": root_name, # TODO: replace this with the non-underscored version
                            "URL": target["URL"],
                            "Info": web_info[-1]["Summary"]
                        }
                        all_outlet_res.append(web_record)
            except:
                # the enumeration would fall here because the website had no information of note and thus never got an entry
                continue
        print("FINISHED PROCESSING: ", root_name)

    print("USER RELATED RESPONSE")
    for i in range(len(all_outlet_res)):
        print(f"""************ Response {i} ************""")
        print(all_outlet_res[i])
        print("************************\n")

    return all_outlet_res

# There are two modes, summarize and search:
#               * SUMMARIZE gets the summary of the webpage
#               * SEARCH pulls information related to the usr statement
def site_crawl(depth, url, usr, results, mode, retry=2):
    page = requests.get(url)
    html_content = extract_html_content(page.text)
    html_links = extract_html_links(page.text, url)
    html_links, links = get_urls_list(html_links)
    print("html text len: ", len(html_content))

    if depth != 0:
        valid = False
        local_retry = retry 
        while local_retry > 0:
            compile_url_prompt = f"""Here is a numbered list of urls found on a news webpage:\n{links}. 
            For each link determine whether it is True or False if the link looks like it would lead to a news article.
            Respond in this format only: {{<number>:<True or False>, <number>:<True or False>, ..., <number>:<True or False>}}"""

            resp = prompt_ivy(compile_url_prompt, ivy_html_system)
            resp_str = extract_response_string(resp).strip()
            if len(resp_str) == 0:
                    local_retry -= 1
                    print("Length of response was 0")
                    continue
            log_ivy(resp)
            print(f"""resp_str[0]: {resp_str[0]}, resp_str[-1]: {resp_str[-1]}""")
            if resp_str[0] == "{" and resp_str[-1] == "}":
                # we have successfully got a dictionary format from Ivy
                print("URL EXTRACTION from: ", url)
                valid = True
                break
            else:
                print("UGHHHHHHH!!!!!!!!!!! Not in dictionary format")
            local_retry -= 1
        if not valid:
            #TODO: determine if something specific needs to be retruned in case of failure
            return
        
        vetted_url = []
        url_ledger = ast.literal_eval(resp_str)
        for i in range(len(html_links)):
            if url_ledger[i + 1]:
                vetted_url.append(html_links[i])

        for vu in vetted_url:
            print("Investigating URL: ", vu)
            site_crawl(depth - 1, vu, usr, results, mode, retry)
        
    # check if there is an existing record
    if mode == SUMMARIZE:
        ivy_prompt = f"""HTML:{html_content} UserInput: Summarize the content of this webpage in 4 sentences. Mention the main topic, key words and any social groups of people it mentions."""
    else:
        ivy_prompt = f"""HTML:{html_content} UserInput:{usr}\nIf there is no relevant information to the UserInput reply only with the word None. """

    resp = prompt_ivy(ivy_prompt, ivy_html_system)

    print(f"""URL: {url}""")
    log_ivy(resp)

    record = {
        "Timestamp": crawl_time,
        "Depth": depth,
        "URL": url,
        "Summary": extract_response_string(resp)
    }
    results.append(record)
    print("Results length: ", len(results))

def html_chunk(html_text, chunk_size=180000):
    start = 0
    resp = []
    if chunk_size >= len(html_text):
      resp.append(html_text)
      return resp
    while start != len(html_text):
        print("Start: ", start)
        idx = html_text.find(">", start + chunk_size) + 1
        resp.append(html_text[start:idx])
        start = idx
        if start == len(html_text) or start == 0:
          break
    return resp

# This function will tell us if we shole re-scrape the website if the 
def redo_crawl_check(record, current_time_str):
    if record == None:
        return True
    record_time = datetime.datetime.strptime(record["Timestamp"], timestamp_format)
    current_time = datetime.datetime.strptime(current_time_str, timestamp_format)
    diff = current_time - record_time
    return diff.days >= timestamp_stale_allowance

def extract_html_links(html_text, root_str):
    soup = BeautifulSoup(html_text, "html.parser")
    
    # Common attributes that contain URLs
    res = ""
    attrs = ["href"]
    excluded_exts = (".js", ".css", ".svg", ".jpg", ".png")

    blocked_paths = ["wp-content", "wp-includes", "assets", "static", "js", "css"]
    
    for tag in soup.find_all('a'):
        for attr in attrs:
            url = tag.get(attr) 
            parsed = urlparse(url)
            path = parsed.path.lower()
            if url and path:
                for b in blocked_paths:
                    if b in path:
                        cont = True
                        break
                if root_str[-1] == "/":
                    # shave off last character
                    root_str = root_str[:len(root_str)-1]
                if "http" not in url:
                    if url[0] != "/":
                        url = url + "/" + url
                    url = root_str + url
                if not path.endswith(excluded_exts):
                    res = res + url
                res = res + "|"
    
    res = res[:-2]
    res = res.split("|")
    return res

def extract_html_content(html_text):
    sections = []
    res = ""

    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup.find_all(["h1", "h2", "h3", "p"]):
        sections.append({
            "type": tag.name,
            "text": tag.get_text(strip=True)
        })
        res = res + tag.get_text(strip=True) + "\n"

    return res

def get_root(root_name):
    # This is funciton works two fold, it checks if the crawl file exists and it returns the record for the root of the file (homepage of the site)
    # The timestamp of all records should be the same so we just need to check that it is within the time allowed for stale data
    # IDEA: Articles are unlikely to change, but the homepage would feature new articles daily, we could keep old ones as a record and reference them later...
    try:
        name = f"""{news_resources}/{root_name}.jsonl"""
        print("getting root of nanma: ", name)
        crawl_file = open(f"""{news_resources}/{root_name}.jsonl""")
        root = json.loads(crawl_file.readline())
        print("get root root: ", root)
        crawl_file.close()
        return root
    except:
        # the record dosent exist, exit
        print("Failed get root open")
        return None

def get_crawl_record(url, root_name):
    # if a record is present returns that record if not returns None
    try:
        crawl_file = open(f"""{news_resources}/{root_name}.jsonl""")

        line = crawl_file.readline()
        # when line is none then that is the end of the file
        while line:
            record = json.loads(line)
            if record["URL"] == url:
                return record
            line = crawl_file.readline()
        crawl_file.close()
    except:
        # the record dosent exist, exit
        return None
    return None

def get_all_crawl_data(filename, community=None):
    res = []
    try :
        crawl_file = open(filename)
        line = crawl_file.readline()

        while line:
            record = json.loads(line)
            if community != None:
                if record["Community"].count("-") == len(record["Community"]):
                        print("General Conversion")
                        record["Community"] = "General"
                if record["Community"] != community:
                        print("Failed community check: ", record)
                        line = crawl_file.readline()
                        continue
            res.append(record)
            line = crawl_file.readline()
        crawl_file.close()
    except:
        print("get all crawl data bad exit")
        return res
    return res

#I am trying to make a social group that pertains to black voters, what things shoudl I include in the mission of my group?
# There are going to be two modes:
#       0. Makes the summaries of all records and returns all records
#       1. Makes summaries and logs records that are from a particular community
def get_summaries_list(filename):
    sum = ""
    idx = 1
    records = []
    try:
        crawl_file = open(filename)

        line = crawl_file.readline()
        # when line is none then that is the end of the file
        while line:
            record = json.loads(line)
            sum = sum + f"""{idx}. {record["Summary"]}\n"""
            records.append(record)
            line = crawl_file.readline()
            idx += 1
            print("Looking at record number: ", idx)
        crawl_file.close()
    except:
        # the record dosent exist, exit
        return sum
    return sum

def get_urls_list(url_list):
    url_list = list(set(url_list))
    res = ""
    idx = 1
    for u in url_list:
        res = res + f"""{idx}. {u}\n"""
        idx += 1
    return url_list, res

def prompt_ivy(query_prompt, ivy_sys):

    response = sage.generate(
        model = ivy_model,
        system = ivy_sys,
        query = query_prompt,
        temperature = ivy_temperature,
        session_id = ivy_session_id,
    )

    return response


### ----------------------------------------------------------------------------------------------------
### Logging Functions, Assess Question         -
### ----------------------------------------------------------------------------------------------------

def log_user(file, text, verbose=verbose):
    phrase = "Anon: " + text + "\n\n"
    file.write(phrase)
    
    if(verbose):
        print(phrase)

def log_sage(file, response, rag_context, verbose=verbose, display_rag=display_rag):
    phrase = f"""Sage: {extract_response_string(response)}\n"""
    
    file.write(phrase)
    
    if(verbose):
        print(phrase)
    if(display_rag == 1):
        print(f"""\n******************\nRag_context: {rag_context} \nRag_context_length: {len(rag_context)} \n******************\n\n""")
    elif(display_rag == 2):
        print(f"""\n******************\nRag_context_length: {len(rag_context)} \n******************\n\n""")

def log_ivy(response, verbose=verbose):
    phrase = f"""Ivy: {extract_response_string(response)}\n"""    
    # file.write(phrase)

    if(verbose):
        print(phrase)

def extract_response_string(response):
    if isinstance(response, dict):
        res = response.get("result")
    elif isinstance(response, tuple):
        res = response[0]["result"]
    else:
        res = response
    
    return res

### ----------------------------------------------------------------------------------------------------
# Command Line Interface
### ----------------------------------------------------------------------------------------------------

def run_cli():
    if not setup_sage():
        print("An error occurred when setting up this application.")
        sys.exit(1)

    with open(f"log-{timestamp}.txt", "w", encoding="utf-8") as file:
        # Intro
        intro = get_intro()
        log_sage(file, intro, "")

        print(str(timestamp))
        usr = input("Type your response here: ")

        while usr != "quit":
            # Log user input
            log_user(file, usr)

            # Core chat call
            result = chat_with_sage(usr)

            # # Log and print answer
            log_sage(file, result["answer"], result["rag_context"])

            # # Show sources if they exist
            if result["sources"]:
                print("\nCitation Summary:\n")
                log_sage(file, result["sources"], "")
            else:
                print("WARNING: No vetted resources were used to produce the information above")

            # Next input
            usr = input("Type your response here: ")


if __name__ == '__main__':
    run_cli()
