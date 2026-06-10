from openai import AzureOpenAI
from dotenv import load_dotenv
import os


load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
    )


response = client.embeddings.create(
    input="What is Kubernetes pod ?",
    model="embedding",
)
print("Embedding created successfully!")
print(f" Length: {len(response.data[0].embedding)}")
