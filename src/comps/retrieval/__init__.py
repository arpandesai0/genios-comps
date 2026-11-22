"""Retrieval: rank companies by description similarity and choose k peers with reasons."""

from comps.retrieval.base import Index, Retriever
from comps.retrieval.select import NearDuplicates, Pick, Selection, Skip, normalize_description, select_peers
from comps.retrieval.tfidf import TfidfRetriever

__all__ = [
    "Index",
    "NearDuplicates",
    "Pick",
    "Retriever",
    "Selection",
    "Skip",
    "TfidfRetriever",
    "normalize_description",
    "select_peers",
]
