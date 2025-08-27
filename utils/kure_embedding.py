import os
import re
import pickle
import pandas as pd
import torch
from dotenv import load_dotenv
from langchain.vectorstores import FAISS
from langchain.schema import Document
from langchain.document_loaders import PDFPlumberLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer
from transformers import AutoModel, AutoTokenizer
from typing import List
from langchain.embeddings.base import Embeddings


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class KUREEmbedding(Embeddings):
    def __init__(self, model_name="nlpai-lab/KURE-v1"):
        self.model = SentenceTransformer(model_name, trust_remote_code=True).to(device)

    def embed_documents(self, texts):
        return self.model.encode(texts, convert_to_numpy=True)

    def embed_query(self, text):
        return self.embed_documents([text])[0]