from openai import OpenAI
import pdfplumber
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

path_apiKEY = r'' #I suggest you to create a txt with your API KEY and then extract it from there
openRouter_path = "https://openrouter.ai/api/v1"

def read_apiKEY(txtFile):
    with open(f'{txtFile}','r',encoding='utf-8') as file:
        apiKEY = file.read()
        return apiKEY

def read_pdf_files(pdf_file):
    full_text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
    return full_text.strip()


def promt_analize(type, rubric, document):
    content = f"Con base a la rúbrica evalúa el siguiente {type}; dame fortalezas, áreas de oportunidad y muy breves sugerencias de mejora. Rúbrica: {rubric} {type}: {document}. Recuerda darme el contenido en español."

    return content

def chat_with_deepseek(content):
    client = OpenAI(api_key=read_apiKEY(path_apiKEY), base_url=openRouter_path)


    chat = client.chat.completions.create(
        model = "deepseek/deepseek-r1:free",
        messages = [
            {
                "role":"user",
                "content": content
            }
        ]
    )

    return chat.choices[0].message.content

def generate_pdf(file_name):

    c = canvas.Canvas(file_name, pagesize=letter)

    c.setFont

