from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get Azure Search service details from environment variables
search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY")
)

def parse_documents(file_path):
    documents = []
    current_content = [] 

    # Create a SearchClient
    credential = AzureKeyCredential(search_admin_key)
    search_client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)

    # upload k8s_error_md from knowledge_base directory
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
        sections = content.split("---")
        # generate unique id for each document
        doc_id = 0
        for section in sections:
            if not section:
                continue
            # append everything after ## and look for terminator as ---"
            current_content.append(section)
            response = client.embeddings.create(input=section, model="embedding")
            if current_content:
                documents.append({
                    "id": str(f"chunk-{doc_id:03d}"),
                    "content": "\n".join(current_content).strip(),
                    "content_vector": response.data[0].embedding
                })
                doc_id += 1
            current_content = []

    # Upload documents to the search index
    try:
        result = search_client.upload_documents(documents)
        print(f"Documents uploaded successfully: {result}")
    except Exception as e:
        print(f"Error uploading documents: {e}")


def main():
    file_path = "knowledge_base/k8s_errors.md"
    parse_documents(file_path)

if __name__ == "__main__":
    main()