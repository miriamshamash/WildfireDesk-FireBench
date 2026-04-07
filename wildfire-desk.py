from build.lib.llmproxy import LLMProxy
import time
import datetime
import sys
from string import Template
from pathlib import Path
import requests

### ----------------------------------------------------------------------------------------------------
### System Settings      -
### ----------------------------------------------------------------------------------------------------

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
verbose = True
display_rag = 0
chatbot_democracy_resources_directory = "sage-resources/democracy-chatbot-resources"
chatbot_wildfire_resources_directory = "sage-resources/wildfire-resources"
sage_instructions_directory = "sage-resources/sage-instructions"
upload_resources = False

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
### Sage Settings        -
### ----------------------------------------------------------------------------------------------------

ivy = LLMProxy()
ivy_model = 'gemini-2.5-flash-lite'
# ivy_html_system = f"""You will receive the raw HTML of a webpage. Extract the key findings, important topics, and any key dates. Respond briefly and clearly."""
ivy_html_system = f"""You will receive the raw HTML of a webpage and user input in the format HTML:<HTML> UserInput:<usr>. Extract the key findings from the webpage that is related to the user input. Respond briefly and clearly."""
# ivy_discern_system = f"""You will receive a question, first answer with either 'Yes' or 'No'. Then respond with a reason in the format: Why: <reason>."""
ivy_discern_system = f"""respond in the format <Yes or No>|<reason why>"""
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
        "rag_context": rag_context
    }

def search_web(file, usr):
    # I propose our web crawler be named Ivy! This is a crawling and climbing vine that (unfortunately) can spread
    # fires, especially in california

    #1. determine if this request needs a websearch to local news
    # TODO: try the question: Does the info from the user need information from local news services to be satisfied
    # TODO: try, is the information the user gave in relation to current events / imply a relation to current events?
    #              If yes then search local news services
    # discern_query = f"""This is a query sent in by a user: {usr}\nwould answering the above query benefit from information from local news coverage?"""
    # discern_query = f"""This is info sent in by a user: {usr}\nis the information above in relation to current events?"""
    
    # discern_query = f"""The user said this: {usr}\nwould an response to the above benefit from information from local news coverage?"""

    # resp = prompt_ivy(discern_query, ivy_discern_system)
    # log_ivy(file, resp)
    # response_parts = extract_response_string(resp).split("|")
    # if len(response_parts) != 2:
    #     # Something has gone wrong with formatting, dont conduct internet search
    #     return
    # elif response_parts[0] != "Yes":
    #     print("No internet search was deemed necessary")
    #     return

    #1.5, ask Sage what area is important to look for info in?
    # Idea: if sage does not know the relevant area, pause this process and have Sage ask the user follow up questions
    #           then report this info to 

    # 1. Fetch relevant webpages
    url = "https://thesunreporter.com/"
    page = requests.get(url)
    html_text = page.text
    # print(html_text)

    # compile_url_prompt = "return all the URLs that relate to news articles in this format: [<url>, <url>, ... <url>]"

    # Idea: attach a timestamp to the stored html pages and if its older than X hours, re-fetch

    # # Systematically go through each webpage
    # combo_prompt = f"""HTML:{html_text} UserInput:{usr} """
    # resp = prompt_ivy(combo_prompt, ivy_html_system)
    # log_ivy(file, resp)
    site_crawl(1, file, url, usr)

    # IDEA: hve a depth map so that we dont have to re-compile the links every time we come in

def site_crawl(depth, file, url, usr, retry=2):
    page = requests.get(url)
    html_text = page.text
    local_retry = retry
    print("html text len: ", len(html_text))

    if depth != 0:
        valid = False
        while local_retry > 0:
            compile_url_prompt = "return all the URLs that relate to news articles in this format: [<url>, <url>, ... <url>]"
            combo_prompt = f"""HTML:{html_text} UserInput:{compile_url_prompt} """
            resp = prompt_ivy(combo_prompt, ivy_html_system)
            resp_str = extract_response_string(resp).strip()
            if len(resp_str) == 0:
                local_retry -= 1
                print("Whomp!!")
                continue
            log_ivy(file, resp)
            print(f"""resp_str[0]: {resp_str[0]}, resp_str[-1]: {resp_str[-1]}""")
            if resp_str[0] == "[" and resp_str[-1] == "]":
                #we have a proper array returned
                # While it may be more efficient ot put it directly in list format with no braces having the 
                # bracketed form makes it easier for the LLM to relate to a structure and gives us an easy thing
                # to check for propoer formation
                print("URL EXTRACTION from: ", url)
                valid = True
                break
            else:
                print("UGHHHHHHH!!!!!!!!!!!")
            local_retry -= 1
        if not valid:
            #TODO: determine if something specific needs to be retruned in case of failure
            return
        url_list = resp_str[1:-1].split(",")
        for u in url_list:
            # each url is encased with brackets so we have to strip those off as well...
            print("Investigating URL: ", u, " after splitting: ", u.split('"'))
            site_crawl(depth - 1, file,  u.split('"')[1], usr, retry)

    search_prompt = f"""HTML:{html_text} UserInput:{usr} """
    resp = prompt_ivy(search_prompt, ivy_html_system)
    print(f"""URL: {url}""")
    log_ivy(file, resp)

#what is happening to this community's students    

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

def log_ivy(file, response, verbose=verbose):
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
    # if not setup_sage():
    #     print("An error occurred when setting up this application.")
    #     sys.exit(1)

    with open(f"log-{timestamp}.txt", "w", encoding="utf-8") as file:
        # Intro
        # intro = get_intro()
        # log_sage(file, intro, "")

        usr = input("Type your response here: ")

        while usr != "quit":
            # Log user input
            log_user(file, usr)

            search_web(file, usr)

            # Core chat call
            # result = chat_with_sage(usr)

            # # Log and print answer
            # log_sage(file, result["answer"], result["rag_context"])

            # # Show sources if they exist
            # if result["sources"]:
            #     print("\nCitation Summary:\n")
            #     log_sage(file, result["sources"], "")
            # else:
            #     print("WARNING: No vetted resources were used to produce the information above")

            # Next input
            usr = input("Type your response here: ")


if __name__ == '__main__':
    run_cli()

# sample statements
#
# how would i organize a local group involving wildfires? 
# I want to organize a neighborhood group focused on wildfire recovery actions, I have not contacted any local authorities.
# the purpose is to invite teh neigbors to a meeting, they are adults and community members, I want a standard format which i can subsititute roles n placeholders
#
#
