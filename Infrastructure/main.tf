terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0" # Use the appropriate version for your project
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-devopswithai-tfstate"
    storage_account_name = "tfstate7i2czd"
    container_name       = "k8sassistant"
    key                  = "k8sassistant.tfstate"
  }
}

provider "azurerm" {
  features {}
}


data "azurerm_kubernetes_cluster" "k8s_assistant_rag_aks" {
  name                = "aks-devopswithai"
  resource_group_name = "rg-devopswithai"
}

data "azurerm_container_registry" "k8s_assistant_rag_acr" {
  name                = "k8sassistantrag"
  resource_group_name = "rg-k8s-assistant"
}

data "azurerm_cognitive_account" "openai" {
  name                = "aoai-k8s-assistant"
  resource_group_name = "rg-k8s-assistant"
}

data "azurerm_search_service" "search" {
  name                = "srch-k8s-assistant"
  resource_group_name = "rg-k8s-assistant"
}

resource "azurerm_user_assigned_identity" "aks_identity" {
  location            = data.azurerm_kubernetes_cluster.k8s_assistant_rag_aks.location
  name                = "rag-app-identity"
  resource_group_name = data.azurerm_kubernetes_cluster.k8s_assistant_rag_aks.resource_group_name
}

resource "azurerm_federated_identity_credential" "aks_federated_identity" {
  name                      = "aks-federated-identity"
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = data.azurerm_kubernetes_cluster.k8s_assistant_rag_aks.oidc_issuer_url
  user_assigned_identity_id = azurerm_user_assigned_identity.aks_identity.id
  subject                   = "system:serviceaccount:kubernetes-assistant:k8s-service-account"
}

resource "azurerm_role_assignment" "acr_pull" {
  principal_id         = azurerm_user_assigned_identity.aks_identity.principal_id
  role_definition_name = "AcrPull"
  scope                = data.azurerm_container_registry.k8s_assistant_rag_acr.id
}

resource "azurerm_role_assignment" "openai_user" {
  principal_id         = azurerm_user_assigned_identity.aks_identity.principal_id
  role_definition_name = "Cognitive Services OpenAI User"
  scope                = data.azurerm_cognitive_account.openai.id
}

resource "azurerm_role_assignment" "search_index_data_reader" {
  principal_id         = azurerm_user_assigned_identity.aks_identity.principal_id
  role_definition_name = "Search Index Data Reader"
  scope                = data.azurerm_search_service.search.id
}
