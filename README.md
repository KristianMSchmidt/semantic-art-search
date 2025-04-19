# Semantic Art Search 🎨🔍

**Discover art through meaning, not just keywords.**

[Semantic Art Search](https://semantic-art-search.kristianms.com) is a vector-based search engine for exploring artworks across multiple museum collections. Instead of relying on traditional metadata, this tool enables **semantic** discovery of art using machine learning.

Currently, it includes artworks from:

- The **Danish National Gallery (SMK)**
- The **Cleveland Museum of Art (CMA)**

## 🔎 How It Works
Semantic Art Search offers two ways to explore artworks:
- **Search by text** – Describe what you're looking for in natural language, and find paintings that match the meaning. The search engine understands short phrases and abstract concepts, so go ahead and try queries like *"Ancient Rome"*, *"War"*, or *"Reading child"*.
- **Find similar** – Select an artwork and discover visually or thematically related pieces.

You can **limit your search to a specific museum** (SMK or CMA), or perform a **cross-museum search** to discover related artworks across collections.

## 💡 Pro Tip: Refining Your Search
For even better results, try combining both search methods:
1. **Start with a text search** – Enter a broad description (e.g., a theme or motif).
2. **Refine with "Find Similar"** – Select the artwork that best fits your intent and discover related pieces.

## 🖼️ Behind the Scenes
The system uses **CLIP, a multimodal neural network**, to transform both images and text into a shared vector space. Searches are performed using **vector-based nearest neighbor retrieval**, enabling more intuitive and meaningful results.

Unlike traditional search methods, **this system does not use titles, artist names, or other metadata** — it relies entirely on the **visual and semantic content** of the artworks.

Currently, **text search is only available in English** due to the model's training data. However, multilingual support could be added by using a larger model trained on multiple languages.

## 🎨 Artwork Coverage
The search covers selected artworks from participating museums that:
- Are in the **public domain**
- Have a **photograph available** in the museum database

Not all types of artworks from the selected museums are included yet, but the dataset may expand in the future.

## 🙌 Acknowledgments
This project is made possible by the **open data initiatives** of the participating museums:

- The **Danish National Gallery (SMK)** – Explore their full collection at [open.smk.dk](https://open.smk.dk/)
- The **Cleveland Museum of Art (CMA)** – Browse their artworks at [clevelandart.org](https://www.clevelandart.org/)

