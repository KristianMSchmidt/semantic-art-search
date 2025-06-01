# Semantic Art Search 🎨🔍

**Discover art through meaning — not just keywords.**

[Semantic Art Search](https://semantic-art-search.com) is an open-source, vector-based search engine for exploring artworks across multiple museum collections. Instead of relying on traditional artwork metadata such as title or description, this tool enables intuitive and flexible discovery of art using machine learning. It allows you to find artworks based on their visual and conceptual content, making it easier to explore themes, styles, and connections across different museums.

Currently, it includes artworks from:

- The **Danish National Gallery (SMK)**
- The **Cleveland Museum of Art (CMA)**
- The **Rijksmuseum Amsterdam (RMA)**

## 🔎 How It Works

There’s just **one unified search bar** — you can write what you're looking for in natural language (e.g., *"Ancient Rome"*, *"blue dress"*, *"mourning"*) and instantly see artworks that match the meaning.

You can also paste an artwork’s **inventory number** into the same field to find visually or thematically similar artworks. 

When you search, the **entire collection is ranked** by how closely each artwork matches your query — the most relevant results appear first, but you can scroll though them all. 

You can:
- **Search across multiple museums** or limit to just one
- **Filter by work type** (e.g., paintings, drawings, prints)
- **Jump from any artwork to visually similar ones** in one click 

Note: filters are based on metadata, but the ranking of search results is not.

## 🤔 Why Not Just Use Metadata?

Metadata can be limiting — not everything you're looking for will be in an artwork’s title or description. Semantic Art Search helps you discover works that *feel* like what you meant — even if the artist or museum never used those exact words.

For example:
- Searching *"Rembrandt"* brings up artworks painted by Rembrandt, in his style, or even portraits of people who resemble him — across multiple collections.
- Searching *"Shipwreck in a storm"* can find turbulent seascapes, even if that exact phrase doesn’t appear in the metadata.

## 🌍 Examples of What You Can Do

- **Find stylistic connections across collections**  
  → What’s the most similar artwork in Rijksmuseum to your favorite piece at SMK?

- **Explore themes or moods**  
  → Try searches like *"sorrow"*, *"revolution"*, or *"moonlight"*.

- **Jump into a cluster of visually similar works**  
  → Just click **“Find similar”** on any artwork.

## 🧠 Behind the Scenes

The system uses **CLIP**, a multimodal neural network, to embed both images and text into a shared vector space. It then performs **vector-based nearest neighbor search** to return the most semantically relevant artworks.

This means:
- The search engine "understands" visual style and meaning, not just keywords.
- Results are based on similarity in visual or conceptual content, not labels.

Currently, **search queries must be in English**, but multilingual support is possible in the future.

## 🎨 Artwork Coverage

The search includes artworks that:
- Are in the **public domain**
- Have a **digital image** available in the museum’s dataset

The selection will grow over time as more data is integrated.

## 🙌 Acknowledgments

This project is made possible by the **open data initiatives** of the participating museums:

- [The Danish National Gallery (SMK)](https://open.smk.dk)
- [The Cleveland Museum of Art (CMA)](https://www.clevelandart.org)
- [The Rijksmuseum Amsterdam (RMA)](https://www.rijksmuseum.nl/en/collection)

## 📬 Get in Touch

If you have questions, feedback, or ideas — or want to contribute — feel free to reach out:

- **Email**: [kmollerschmidt@gmail.com](mailto:kmollerschmidt@gmail.com)  
- **LinkedIn**: [Kristian Møller Schmidt](https://www.linkedin.com/in/kristian-m%C3%B8ller-schmidt-516b9170/)
