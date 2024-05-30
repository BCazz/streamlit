import re
import time
import openai
import calendar
import datetime as dt
import streamlit as st
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

######################################################################################################## Login / Authorization ###################################################################################3

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

   ########################################################################################## Declare Connections ########################################################################################3
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

    ########################################################################################################### Set Prompts ####################################################################################################

    weather_prompt = f"Weather Prompt --> Please provide me with a commentary on weather developments that have occurred that could impact power or natural gas market. Weather developments of interest include those that relate to waves of oncoming or upcoming heat and or cold fronts. Other developments of interest include those that pertain to the increase or decrease of heating degree days, often referred to as 'HDDs', and/or the increase or decrease of cooling degree days, often referred to as 'CDDs'."
    economic_prompt = f"Economic Prompt --> Please provide me with a commentary on economic developments that have occurred which could impact power or natural gas demand."
    data_center_prompt = f"Data Center Prompt --> Please provide me with a commentary on data center developments that have occurred. Data center developments of interest are the annoucements of new planned investments and deals for power supply to data centers. Other areas of interest also include news on the progression of data center build outs or financings. Also of interest is news on how data centers can drive an increase in electricty demand."
    lng_prompt = f"LNG Prompt --> Please provide me with a commentary on LNG developments that have occurred. LNG developments of interest include those pertaining to outages for export terminals ending, the volume of exports increasing, and progress on LNG terminals under development. Please exclude any commentary on LNG terminal outages being extended or occuring."
    technicals_prompt = f"Market Technicals Prompt --> Please provide me with a commentary on technical developments that have occurred. Technical developments of interest include those relevant to market participant positioning such as investors, market participants, and speculators decreasing, covering, or adding to positions."
    production_prompt = f"Production Prompt --> Please provide me with a commentary on the developments that impacted natural gas production."
    storage_prompt = f"Storage Prompt --> Please provide me with a commentary on the developments that impacted the levels of natural gas in storage."

    ######################################################################################################### Take User Inputs ########################################################################################3

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
        st.title("AP Market Commentary Vector Search")
    with spacer3:
        st.write("")

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

    if 'vector_search_submitted' not in st.session_state:
        st.session_state['vector_search_submitted'] = False
    
    if 'vector_search_completed' not in st.session_state:
        st.session_state['vector_search_completed'] = False

    # Callback function to run the vector search
    def run_vector_search():
        # checking if the data is accurately submitted
        if not st.session_state.user_prompt or not st.session_state.start_date or not st.session_state.end_date:
            st.error("Please select a Start Date, End Date, ISO, and a request for the query.")
        else:
            # contuing with search if accurately submitted
            
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
                    'numCandidates': 500,
                    'limit': 10
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

            st.write(f"Search Results Below:\n\n{context}")

    # Display the series of data requests/options for the RAG
    with st.form("vector_search"):
        
        st.write("Please select the time period for which you would like your response to be grounded.")
        st.date_input("Start Date", key="start_date")
        st.date_input("End Date", key="end_date")

        st.write("")
        st.write("Please select the ISO for which you would like your response to be grounded if applicable.")
        isos = ['N/A','ERCOT','NYISO','PJM','MISO']
        iso = st.radio("ISOs:", options=isos, index=isos.index(st.session_state.iso), horizontal=False, key='iso')
        st.write("")

        with st.expander("Click to see some search ideas"):
            st.write(f"{weather_prompt}\n\n{economic_prompt}\n\n{data_center_prompt}\n\n{lng_prompt}\n\n{technicals_prompt}\n\n{production_prompt}\n\n{storage_prompt}")

        st.write("Please write your query for the Vector Search.")
        st.text_area("Type Below:", height=250, key="user_prompt")
        
        st.form_submit_button("Submit", on_click=run_vector_search)
