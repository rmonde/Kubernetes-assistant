from azure.search.documents.indexes.models import SearchIndex, SearchField, SearchableField, VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration 
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def create_search_index():
    # Get Azure Search service details from environment variables
    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

    # Create a SearchIndexClient
    credential = AzureKeyCredential(search_admin_key)
    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)

    # Define the search index schema
    fields = [
        SearchField(name="id", type="Edm.String", key=True),
        SearchableField(name="content", type="Edm.String"),
        SearchField(name="content_vector", type="Collection(Edm.Single)", vector_search_dimensions=1536, vector_search_profile_name="default")
    ]

    # Define vector search configuration
    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="default",
                algorithm_configuration_name="hnsw"
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw"
            )
        ]
    )

    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)

    # Create the search index
    try:
        index_client.create_index(index)
        print(f"Search index '{index_name}' created successfully.")
    except Exception as e:
        print(f"Error creating search index: {e}")

def main():
    create_search_index()

if __name__ == "__main__":
    main()