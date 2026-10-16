import os
import json
from langchain.agents import create_agent
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.tools import tool
from prompt import system_msg
import base64
import io
import requests
from PIL import Image as im

load_dotenv()

#openai:gpt-4o-mini
#llama3.2:3b inventa cosas

os.environ["OPENAI_API_KEY"]= os.getenv("OPENAI_API_KEY")

llm = ChatOllama(model="ornith-1.5:9b")


@tool("List_files", description="Tool made for show the folders and files of a path")
def list_files(path:str) -> list:
    """Return the list of files in the path provided"""
    archivos = os.listdir(path)
    return archivos

@tool("read_file", description="Tool made for show the content a file in a file")
def read_file(path:str) -> list:
    """Return the content of a file"""
    with open(path, 'r', encoding='utf-8') as archivo:
        contenido = archivo.read()
        return contenido

@tool("write_json", description="tool made for write results in files .json")
def write_json(result: dict):
    """Write in a json file"""
    with open("modelo.json", "w", encoding="utf-8") as f:
        json.dump(result,f, indent=4, ensure_ascii=False)

agent = create_agent(
    model="openai:gpt-5.4", #"openai:gpt-4o-mini", #llm - para hecerlo locar gpt-5.3-codex
    tools=[list_files, read_file, write_json],
    #prompt="you are a helpful assistant",
)


stream =  agent.stream_events({
    "messages":[system_msg, {
        "role": "user",
        "content": r"Hola chat necesito el modelo de datos de este proyecto: /Users/ander/Documents/an0010001_conc_transportes para su modelo de datos, es un modelo orquestador"
    }
    ]
}, version="v3")


for message in stream.messages:

    finalized = message.tool_calls.get()

    print("\n")
    print("\n")
    print("\n")
    print("========================================================")

    if finalized:
        print(f"finalized tool calls: {finalized}")


    for delta in message.reasoning:
        print(f"[thinking] {delta}", end="", flush=True)


    for delta in message.text:
        print(delta, end="", flush=True)



final_state = stream.output


