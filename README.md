# Semantic Art Search 🎨🔍

**Discover art through meaning, not just keywords.**

[Semantic Art Search](https://semantic-art-search.kristianms.com) is a vector-based search engine for exploring artworks from the Danish National Gallery (SMK). Instead of relying on traditional metadata, this tool enables **semantic** discovery of art using machine learning.

## 🔎 How It Works
Semantic Art Search offers two ways to explore artworks:
- **Search by text** – Describe what you're looking for in natural language, and find paintings that match the meaning.
- **Find similar** – Select an artwork and discover visually or thematically related pieces.

## 🖼️ Behind the Scenes
The system uses **CLIP, a multimodal neural network**, to transform both images and text into a shared vector space. Searches are performed using **vector-based nearest neighbor retrieval**, enabling more intuitive and meaningful results.

## 🎨 Artwork Coverage
Currently, the search covers a **subset of SMK's collection**, including artworks that:
- Are in the **public domain**
- Have a **photograph available** in the SMK database

Not all types of artworks are included yet, but the dataset may expand in the future.

## 🙌 Acknowledgments
This project is made possible by **SMK’s open data initiative**, which provides free access to digitized artworks and metadata. You can explore the full collection with keyword-based search at [open.smk.dk](https://open.smk.dk/).
