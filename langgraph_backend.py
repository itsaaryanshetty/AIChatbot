from importlib import metadata
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage #base message is the base class for all messages (FOundational )
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from dotenv import load_dotenv
import sqlite3
import requests


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials  #handles outh credentials 
from google_auth_oauthlib.flow import InstalledAppFlow  #this is used to authenticate and authorize a user for google services
from googleapiclient.discovery import build
import os   #file path handling and accessing environment variables

load_dotenv()

# Google Calendar setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
 
def get_calendar_service():    #Authenticates and returns a Google Calendar service object, which can be used to interact with the user's Google Calendar.
    """Authenticate and return Google Calendar service"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    service = build('calendar', 'v3', credentials=creds)
    return service


llm = HuggingFaceEndpoint(
    repo_id = "Qwen/Qwen2.5-72B-Instruct",
    task = "conversational"
)

model = ChatHuggingFace(llm=llm)

search_tool  = DuckDuckGoSearchRun(region="us-en")

@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}

@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA') 
    using Alpha Vantage with API key in the URL.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=K5E567N0QF57HI3V"
    r = requests.get(url)
    return r.json()

@tool
def create_calendar_event(
    title: str,
    start_datetime: str,
    end_datetime: str,
    description: str = "",
    location: str = ""
) -> dict:
    """
    Create a Google Calendar event.
    
    Args:
        title: Event title/summary
        start_datetime: Start time in ISO format (e.g., "2025-10-30T10:00:00")
        end_datetime: End time in ISO format (e.g., "2025-10-30T11:00:00")
        description: Event description (optional)
        location: Event location (optional)
    
    Returns:
        Dictionary with event details or error message
    """
    try:
        service = get_calendar_service()
        
        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_datetime,
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': 'Asia/Kolkata',
            },
        }
        
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        
        return {
            "success": True,
            "event_id": created_event['id'],
            "title": title,
            "start": start_datetime,
            "link": created_event.get('htmlLink', '')
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def get_calendar_events(
    start_date: str,
    end_date: str,
    max_results: int = 10
) -> dict:
    """
    Retrieve Google Calendar events within a date range.
    
    Args:
        start_date: Start date in ISO format (e.g., "2025-10-30T00:00:00")
        end_date: End date in ISO format (e.g., "2025-11-30T23:59:59")
        max_results: Maximum number of events to return (default: 10)
    
    Returns:
        Dictionary with list of events or error message
    """
    try:
        service = get_calendar_service()
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_date + 'Z',
            timeMax=end_date + 'Z',
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        event_list = []
        for event in events:
            event_list.append({
                'title': event.get('summary', 'No title'),
                'start': event['start'].get('dateTime', event['start'].get('date')),
                'end': event['end'].get('dateTime', event['end'].get('date')),
                'description': event.get('description', ''),
                'location': event.get('location', '')
            })
        
        return {"success": True, "events": event_list, "count": len(event_list)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Youtube Search Tool
@tool
def search_youtube(query: str, max_results: int = 5) -> dict:
    """
    Search for YouTube videos based on a query.
    
    Args:
        query: Search query (e.g., "python tutorial", "how to cook pasta")
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Dictionary with list of videos including title, channel, and video URL
    """
    try:
        youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        if not youtube_api_key:
            return {"success": False, "error": "YouTube API key not found"}
        
        youtube = build('youtube', 'v3', credentials=None, developerKey=youtube_api_key)
        
        search_response = youtube.search().list(
            q=query,
            part='id,snippet',
            maxResults=max_results,
            type='video'
        ).execute()
        
        videos = []
        for item in search_response.get('items', []):
            video_id = item['id']['videoId']
            videos.append({
                'title': item['snippet']['title'],
                'channel': item['snippet']['channelTitle'],
                'description': item['snippet']['description'][:200] + '...',
                'url': f'https://www.youtube.com/watch?v={video_id}',
                'thumbnail': item['snippet']['thumbnails']['default']['url']
            })
        
        return {"success": True, "videos": videos, "count": len(videos)}
    except Exception as e:
        return {"success": False, "error": str(e)}



tools = [search_tool, get_stock_price, calculator, create_calendar_event, get_calendar_events, search_youtube]
llm_with_tools = model.bind_tools(tools)



class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatState):
    messages = state['messages']
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

tool_node = ToolNode(tools)

conn =sqlite3.connect(database='chatbot.db', check_same_thread=False)
# Checkpointer
checkpointer = SqliteSaver(conn=conn)

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge("tools", 'chat_node')

chatbot = graph.compile(checkpointer=checkpointer)

def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])

    return list(all_threads)

def delete_thread(thread_id):
    """Delete a specific thread from the database"""
    try:
        # Remove all checkpoints for this thread
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM checkpoints WHERE thread_id = ?",
            (thread_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting thread: {e}")
        return False
