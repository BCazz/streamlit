import re
import time
import openai
import calendar
import datetime as dt
import streamlit as st
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

############################################################################### Login / Authorization ###################################################################################3

# Initialize session state variables
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'pwd' not in st.session_state:
    st.session_state['pwd'] = ""
if 'credentials_correct' not in st.session_state:
    st.session_state['credentials_correct'] = False
if 'form_submitted' not in st.session_state:
    st.session_state['form_submitted'] = False
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Callback function to check login credentials
def check_credentials():
    st.session_state['form_submitted'] = True
    if (
        st.session_state['username'] == st.secrets['streamlit_credentials']['username']
        and
        st.session_state['pwd'] == st.secrets['streamlit_credentials']['password']
    ):
        st.session_state['credentials_correct'] = True
        st.session_state['logged_in'] = True
        st.session_state['username'] = ""
        st.session_state['pwd'] = ""
    else:
        st.session_state['credentials_correct'] = False

# Display login form
def display_login_form():
    with st.form("login_form"):
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="pwd")
        st.form_submit_button("Login", on_click=check_credentials)

# Login logic
if not st.session_state['logged_in']:
    if not st.session_state['credentials_correct'] and not st.session_state['form_submitted']:
        display_login_form()
    elif not st.session_state['credentials_correct'] and st.session_state['form_submitted']:
        display_login_form()
        st.error("Invalid password")
else:    
    # code moves on

    ################################################################################# ChatBot #################################################################################################################3
    ################################################################################ Set Prompts ####################################################################################################

    system_prompt = """
    You are a commodity research analyst that helps other understand commodity market key developments and news that impact the specified market.
    Your answers should be one to three paragraphs depending on how many key developments there is to cover. The more the more key developments the longer the response should be and the less key developments the shorter the response should be.
    A successful response will briefly describe a key development and explain why that development would impact the commodity market pricing for each key development. 
    For for each key development cite the source which points to its occurrence. The source should be cited in the following format [source: "SOURCE"].
    The write-up must have proper grammar.
    The write-up can use jargon as you should assume the reader is modestly knowledgeable of the market.
    """
    instructions = """
    Use the CONTEXT above to respond to the user's REQUEST.
    Ground your response in the facts that CONTEXT provides.
    Do not make up any stories or market data. Only use the market data which is provided by CONTEXT and site sources in your response.
    If CONTEXT does not contain enough information to respond to the REQUEST return "I need more information to provide an answer".
    """

    ############################################################################### Declare Connections ########################################################################################3
    # setting credentials for MongoDB and OpenAI
    for key in ('uri', 'open_ai_api_key'):
        if key not in st.session_state:
            st.session_state[key] = ""

    # Get secrets from Streamlit secrets
    uri = st.secrets["mongodb"]["uri"]
    openai_api_key = st.secrets["openai"]["api_key"]

    # Set MongoDB client
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client.MarketCommentaries

    # Set OpenAI API key
    openai.api_key = openai_api_key

    ############################################################################### Take User Inputs ########################################################################################3

    # adding titles and instructions
    image_placeholder = st.empty()
    spacer1 = st.empty()
    spacer2 = st.empty()
    title_placeholder = st.empty()
    spacer3 = st.empty()

    # Display the elements using placeholders
    # with image_placeholder:
    #     st.image("ap_logo.png", use_column_width=True)
    with spacer1:
        st.write("")
    with spacer2:
        st.write("")
    with title_placeholder:
        st.title("AP Market Analyst Chatbot")
    with spacer3:
        st.write("")

    # initialize the convo btwn ChatGPT and User -- input uses contextualized user prompt and output uses regular user prompt
    if 'conversation_input' not in st.session_state:
        st.session_state.conversation_input = [{"role": "system", "content": system_prompt}]
    if 'conversation_output' not in st.session_state:
        st.session_state.conversation_output = [{"role": "system", "content": system_prompt}]

    # Input fields for start date, end date, ISO, an duser_prompt
    if 'user_prompt' not in st.session_state:
        st.session_state.user_prompt = ""

    if 'iso' not in st.session_state:
        st.session_state.iso = "N/A"

    # Calculate the default dates
    today = dt.date.today()
    bom = today.replace(day=1)
    _, last_day = calendar.monthrange(today.year, today.month)
    eom = today.replace(day=last_day)

    if 'start_date' not in st.session_state:
        st.session_state.start_date = bom

    if 'end_date' not in st.session_state:
        st.session_state.end_date = eom

    if 'rag_form_submitted' not in st.session_state:
        st.session_state['rag_form_submitted'] = False
    
    if 'rag_form_completed' not in st.session_state:
        st.session_state['rag_form_completed'] = False

    # Callback function to check if the data submission for the RAG is complete
    def check_rag_form():
        st.session_state['rag_form_submitted'] = True
        if not st.session_state.user_prompt or not st.session_state.start_date or not st.session_state.end_date:
            st.session_state['rag_form_completed'] = False
        else:
            st.session_state['rag_form_completed'] = True

    # Display the series of data requests/options for the RAG
    def display_rag_form():
        with st.form("rag_form"):
            
            st.write("Please select the time period for which you would like your response to be grounded.")
            st.date_input("Start Date", key="start_date")
            st.date_input("End Date", key="end_date")

            st.write("")
            st.write("Please select the ISO for which you would like your response to be grounded.")
            isos = ['N/A','ERCOT','NYISO','PJM','MISO']
            iso = st.radio("ISOs:", options=isos, index=isos.index(st.session_state.iso), horizontal=False, key='iso')
            st.write("")

            st.write("Please write your question for the ChatBot.")
            st.text_area("Type Below:", height=250, key="user_prompt")
            
            st.form_submit_button("Submit", on_click=check_rag_form)

    # check if RAG request is complete 
    if not st.session_state['rag_form_completed']:
        if not st.session_state['rag_form_submitted']:
            display_rag_form()
        elif st.session_state['rag_form_submitted']:
            display_rag_form()
            st.error("Please select a Start Date, End Date, ISO, and a request for the ChatBot.")
    else:
        # Code moves on when the form is completed

    ########################################################################## Feed Inputs into the RAG ########################################################################################3

        def rag(system_prompt,instructions):
            prompt_vector = openai.embeddings.create(
                input=st.session_state.user_prompt,
                model="text-embedding-3-large"
            )

            prompt_vector = prompt_vector.data[0].embedding

            # prepping the data for a vector search (can only run match as the first stage of an aggregation pipeline)
            def data_prep_aggregation_framework(collection_name):
                collection = db[collection_name]

                # need this step b/c streamlit start_date and end_date are DATE objects NOT DATETIME objects which MongoDB needs
                start_date = dt.datetime.combine(st.session_state.start_date, dt.datetime.min.time())
                end_date = dt.datetime.combine(st.session_state.end_date, dt.datetime.min.time())
                iso = st.session_state.iso
                iso = iso.lower()

                match_stage_a = {
                    "$match": {
                        "date": {
                            "$gte": start_date,
                            "$lte": end_date
                        }
                    }
                }

                
                if iso != "n/a" :
                    match_stage_b = {
                        "$match": {
                            "tags": {
                                "$in": [iso]
                            }
                        }
                    }
                else:
                    match_stage_b = {
                        "$match": {}
                    }           
          
                data_prep_pipeline = [
                    match_stage_a,
                    match_stage_b,
                ]

                return data_prep_pipeline

            def update_collection_with_pipeline(source_collection_name, target_collection_name):
                data_prep_pipeline = data_prep_aggregation_framework(source_collection_name)
                new_documents = db[source_collection_name].aggregate(data_prep_pipeline)
                new_documents = list(new_documents)

                # Remove all documents from the target collection
                db[target_collection_name].delete_many({})

                # Insert new documents into the target collection
                if len(new_documents) > 0:
                    db[target_collection_name].insert_many(new_documents)
                else:
                    pass

            update_collection_with_pipeline("Chunked", "TemporaryChunked")
            #update_collection_with_pipeline("NonChunked", "TemporaryNonChunked")

            vector_search_stage = {
                '$vectorSearch': {
                    'index': 'vector_index', 
                    'path': 'vector', 
                    'queryVector': prompt_vector,
                    'numCandidates': 100,
                    'limit': 3
                }
            }

            # semi_chunked_id = 1 if using parent/child approach 0 otherwise
            # option see vector_Search score --> 'score': {'$meta': 'vectorSearchScore'},
            project_stage = {
                '$project': {
                    '_id': 0, 
                    'source': 1,
                    'contents': 1,
                    'semi_chunked_id': 1 
                }
            }

            vector_search_pipeline = [
                vector_search_stage,
                project_stage
            ]

            time.sleep(90)
            #time.sleep(15)


            chunked_docs = db.TemporaryChunked.aggregate(vector_search_pipeline)
            #chunked_docs = db.Chunked.aggregate(vector_search_pipeline) # used for testing
            #non_chunked_docs = db.TemporaryNonChunked.aggregate(vector_search_pipeline)

            ############################################################################################### Parent Child Option/Functionality ##################################################################################################################

            non_chunked_ids = []
            for document in chunked_docs:
                non_chunked_id = document['semi_chunked_id']
                non_chunked_ids.append(non_chunked_id)

            non_chunked_ids = list(set(non_chunked_ids))
            non_chunked_ids = [ObjectId(_id) for _id in non_chunked_ids]

            non_chunked_query = {"_id": {"$in": non_chunked_ids}}
            non_chunked_project = {"_id":0, "contents":1, "source":1}

            non_chunked_docs = db.NonChunked.find(non_chunked_query,non_chunked_project)
            non_chunked_docs = list(non_chunked_docs)

            context = ""
            for doc in non_chunked_docs:
                context += doc["source"] + "\n" + doc["contents"] + "\n\n"

            with st.expander("Click to see the data I based my answer on."):
                st.write(f"{context}")

            ############################################################################################### Feeding Context into the Prompt ##################################################################################################################

            # cleaning up the spacing of the inputs
            prompts = [
                system_prompt,
                st.session_state.user_prompt,
                instructions
            ]

            split_pattern = r'\n|\t'
            for index, prompt in enumerate(prompts):
                prompt = re.split(split_pattern,prompt)
                prompt = [item.strip() for item in prompt]
                prompt = ' '.join(prompt).strip()
                prompts[index] = prompt

            system_prompt = prompts[0]
            modified_user_prompt = prompts[1]
            instructions = prompts[2]

            contextualized_user_prompt = f"CONTEXT:\n{context}REQUEST:\n{modified_user_prompt}\n\nINSTRUCTIONS:{instructions}"

            # append the contextualized prompt and the original prompt to the conversation lists
            st.session_state.conversation_input.append({"role": "user", "content": contextualized_user_prompt})
            st.session_state.conversation_output.append({"role": "user", "content": st.session_state.user_prompt})

            ############################################################################################### ChatGPT Answering Prompt ##################################################################################################################

            # Generate a response
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=st.session_state.conversation_input,
                temperature=.5
            )

            # Extract the response text
            ai_response = response.choices[0].message.content

            st.session_state.conversation_input.append({"role": "assistant", "content": ai_response})
            st.session_state.conversation_output.append({"role": "assistant", "content": ai_response})

            for message in st.session_state.conversation_output:
                if message['role'] == 'user':
                    st.write(f"**You:** {message['content']}")
                elif message['role'] == 'system':
                    pass
                else:
                    st.write(f"**ChatGPT:** {message['content']}")

        # making it so rag is only run once
        if 'rag_run' not in st.session_state:
            st.session_state['rag_run'] = False
        if not st.session_state['rag_run']:
            rag(system_prompt,instructions)
            st.session_state['rag_run'] = True

        ############################################################################################### Follow-up Interface ##################################################################################################################
        
        if 'follow_up_prompt' not in st.session_state:
            st.session_state.follow_up_prompt = ""

        def clear_all():
            image_placeholder.empty()
            spacer1.empty()
            spacer2.empty()
            title_placeholder.empty()
            spacer3.empty()

        clear_all()

        def get_response(conversation_input):
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=conversation_input,
                temperature=1
            )

            ai_response = response.choices[0].message.content

            return ai_response

        def handle_conversation(follow_up_prompt):
            st.session_state.conversation_input.append({"role": "user", "content": follow_up_prompt})
            st.session_state.conversation_output.append({"role": "user", "content": follow_up_prompt})
            ai_response = get_response(st.session_state.conversation_input)
            st.session_state.conversation_input.append({"role": "assistant", "content": ai_response})
            st.session_state.conversation_output.append({"role": "assistant", "content": ai_response})
        
        def follow_up():
            follow_up_prompt = st.session_state.follow_up_prompt
            if follow_up_prompt:
                handle_conversation(follow_up_prompt)
                st.session_state.follow_up_prompt = ""
                #del st.session_state["follow_up_prompt"]

                for message in st.session_state.conversation_output:
                    if message['role'] == 'user':
                        st.write(f"**You:** {message['content']}")
                    elif message['role'] == 'system':
                        pass
                    else:
                        st.write(f"**ChatGPT:** {message['content']}")

        follow_up_prompt = st.text_area("Ask a follow up question:", height=100, key="follow_up_prompt")
        follow_up_button = st.button(label="Submit", type="primary", on_click=follow_up)