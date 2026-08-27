import os
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

@tool("generar_imagen", description="Tool made for return an image with a prompt")
def generar_imagen_tool(codigo_mermaid: str) -> str:
    """Úsala cuando el usuario te pida crear, dibujar o mostrar una imagen."""
   # Codificar el diagrama a base64 seguro para URL
    graphbytes = codigo_mermaid.encode("utf8")
    base64_bytes = base64.urlsafe_b64encode(graphbytes)
    base64_string = base64_bytes.decode("ascii")

    # Obtener la imagen desde la API de Mermaid.ink
    url = f"https://mermaid.ink/img/{base64_string}"
    respuesta = requests.get(url)

    if respuesta.status_code == 200:
        # Abrir y guardar la imagen localmente
        imagen = im.open(io.BytesIO(respuesta.content))
        imagen.save("diagrama.png")
        return "diagram.png"
    else:
        raise ValueError("Error al generar la imagen.")

agent = create_agent(
    model="openai:gpt-4o-mini", #llm - para hecerlo locar gpt-5.3-codex
    tools=[{"type": "web_search"}, list_files, read_file],
    #prompt="you are a helpful assistant",
)


stream =  agent.stream_events({
    "messages":[system_msg, {
        "role": "user",
        "content": r"Hola chat necesito el mermaid de este proyecto: C:\Users\Jhon\OneDrive - Synaptica\Escritorio\transporte\calendarizar2\an0010001-conc-transportes para su modelo de datos, es un modelo orquestador"
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


