from openai import AzureOpenAI
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import os

load_dotenv()

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, 
    "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    # api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_ad_token_provider=token_provider,
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    timeout=60
    )

def embed(question):
    response = client.embeddings.create(
        input=question,
        model="embedding",
    )
    print("Embedding created successfully!")
    print(f" Length: {len(response.data[0].embedding)}")
    return response.data[0].embedding

def search(vector):
    #credential = AzureKeyCredential(os.getenv("AZURE_SEARCH_ADMIN_KEY"))
    search_client = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        credential=credential
    )
    # Define the Vectorized Query
    vector_query = VectorizedQuery(
        fields="content_vector",
        k_nearest_neighbors=3,
        vector=vector
    )
    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query]
    )
    return results

def build_prompt(question, chunk):
    formatted_context = "\n\n---\n\n".join(chunk)
    prompt = f"""
    Question: {question}
    Context: {formatted_context}
    Answer:
    """
    print(prompt)
    result = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {
                "role": "system", 
                "content": "You are a helpful assistant. Use ONLY the provided context to answer the user's question. "
                "If the information is not in the context, say 'I do not know'.Do not add any information beyond what is in the context."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        temperature=0.0,
        max_tokens=500
    )

    return result.choices[0].message.content


def main():
    question = "My pod keeps restarting and the status shows OOMKilled ?"
    embedding = embed(question)
    results = search(embedding)

    # Collect the content from the search results
    # and create a common chunk to pass to the LLM
    chunk = []
    for result in results:
        chunk.append(result["content"])
        
    
    answer = build_prompt(question, chunk)
    print(answer)


if __name__ == "__main__":
    main()
