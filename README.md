# 🔍 Flipper Lite - Curriculum Video Browser

A lightweight, fast web application that helps teachers discover high-quality educational videos aligned to the **White Rose Maths curriculum**.

## ✨ Features

- 🎯 **Curriculum-Aligned**: Browse videos by Year Group, Block, and Small Step
- ⚡ **Lightning Fast**: Pre-computed recommendations load instantly
- 📱 **Mobile-Friendly**: Works on phones, tablets, and desktops
- 🎓 **Quality-Scored**: All videos rated for educational value
- 🚀 **Zero Setup**: No API keys, no installation required

## 🌐 Try It Live

**Coming soon**: [flipper-curriculum.streamlit.app](https://flipper-curriculum.streamlit.app)

## 🏫 Perfect For

- Teachers planning lessons
- Parents supporting home learning
- Tutors finding topic-specific videos
- Schools building resource libraries

## 🛠️ Technology

Built with **Streamlit** for simplicity and speed. No heavy AI dependencies means instant loading and zero cost hosting.

## 💻 Run Locally

```bash
# Install dependencies (only 2 packages!)
pip install -r requirements_tier1.txt

# Launch the app
streamlit run flipper_lite.py
```

Visit `http://localhost:8501` in your browser.

## 📊 How It Works

1. **Pre-computation**: Videos are analyzed once using semantic search and LLM evaluation
2. **CSV Storage**: Best recommendations stored in a simple spreadsheet
3. **Fast Lookup**: App simply reads the CSV - no AI processing at runtime

## 📚 Data Source

Videos curated from educational YouTube channels, with each video scored for:
- Curriculum alignment accuracy
- Teaching quality
- Age-appropriateness
- Content clarity

## 🎯 Curriculum Coverage

- **White Rose Maths** curriculum structure
- Year groups from Reception to Year 6
- All blocks and small steps covered
- Regular updates as curriculum evolves

## 🤝 Contributing

This is a personal project to help teachers. Feedback welcome!

## 📝 License

Educational use. Videos remain property of their respective creators.

## 👨‍💻 About

Created to make finding quality maths teaching videos effortless. Built as **Tier 1** of a two-tier architecture - simple, fast, and free forever.
