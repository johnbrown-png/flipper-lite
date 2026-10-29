# Flipper Service Architecture - Two-Tier Strategy

## 📋 Overview

This document outlines the architecture for transitioning Flipper from a development tool to a production service with two distinct tiers:

- **Tier 1**: Ultra-lightweight curriculum guide (pre-computed, no runtime AI)
- **Tier 2**: Full-featured semantic search (runtime FAISS + LLM)

## 🎯 Tier comparison

| Feature | Tier 1 (Lightweight) | Tier 2 (Full-Featured) |
|---------|---------------------|------------------------|
| **Search Type** | Pre-computed curriculum lookup | Runtime semantic search |
| **AI Processing** | None (CSV lookup only) | FAISS + LLM on every search |
| **Input Method** | Curriculum selectors only | Curriculum + Free text search |
| **Response Time** | <100ms | 2-5 seconds |
| **Data Size** | ~5-50 MB | ~500 MB - 5 GB |
| **Hosting Cost** | Free - $5/month | $50-200/month |
| **Mobile Suitability** | Perfect (ultra-light) | Challenging (heavy) |
| **Target Users** | Teachers following curriculum | Educators seeking any topic |
| **Scalability** | 100,000+ users easily | Limited by LLM API costs |

## 🏗️ Architecture Details

### Tier 1: Lightweight Curriculum Guide

#### Data Flow
```
┌─────────────────────┐
│ Pre-computation     │ (Run once, offline)
│ (One-time process)  │
└──────┬──────────────┘
       │
       ├─ Load FAISS index
       ├─ Load curriculum CSV
       ├─ For each curriculum item:
       │   ├─ Generate embedding
       │   ├─ Search FAISS
       │   ├─ Score with LLM
       │   └─ Save top 5 videos
       │
       ▼
┌─────────────────────────┐
│ precomputed_recommendations.csv │  ◄── Deploy this
│ (Static lookup table)            │
└──────┬────────────────────┘
       │
       ▼
┌─────────────────────┐
│ Tier 1 Web App      │
│ (Streamlit/HTML)    │
├─────────────────────┤
│ • Load CSV          │
│ • Curriculum filter │
│ • Display videos    │
│ • Zero AI calls     │
└─────────────────────┘
```

#### Key Files
- `precompute_curriculum_recommendations.py` - Generates the lookup table
- `flipper_tier1_lightweight.py` - Streamlit app (CSV lookup only)
- `precomputed_recommendations.csv` - The magic data file

#### Deployment Options

**Option A: Streamlit Cloud** ⭐ RECOMMENDED for first version
- **Effort**: 1-2 hours
- **Cost**: FREE
- **Steps**:
  1. Create GitHub repo
  2. Push `flipper_tier1_lightweight.py` + CSV
  3. Connect at share.streamlit.io
  4. Done! You have a URL: `flipper-curriculum.streamlit.app`
- **Pros**: Zero web dev required, you already know Streamlit
- **Cons**: Streamlit branding, limited customization
- **Mobile**: Works but not native app

**Option B: Static Website (Netlify/Vercel)**
- **Effort**: 2-3 days (learning curve)
- **Cost**: FREE
- **Tech**: Convert to HTML/CSS/JavaScript
  - Use a template like [Next.js starter](https://vercel.com/templates)
  - Or pure HTML with [DataTables.js](https://datatables.net/)
- **Pros**: Professional look, fast loading, custom domain
- **Cons**: Need to learn basic web dev
- **Mobile**: Responsive website

**Option C: Android App (Flutter + CSV)**
- **Effort**: 1-2 weeks (steep learning curve)
- **Cost**: $25 (Google Play fee)
- **Tech**: 
  - Flutter (Dart language - similar to Python)
  - Load CSV from assets
  - Build native Android app
- **Pros**: True mobile app, works offline
- **Cons**: Must learn Flutter
- **Tutorial**: [Flutter CSV app tutorial](https://docs.flutter.dev/cookbook)

**Option D: No-Code Tools**
- **Airtable + Softr**: Upload CSV → drag-and-drop website builder ($49/mo)
- **Google Sheets + AppSheet**: Turn spreadsheet into app (free for <10 users)
- **Bubble.io**: No-code app builder with CSV import ($32/mo)

### Tier 2: Full-Featured Semantic Search

This is your current `flipper.py` with enhancements:

#### Architecture
```
┌────────────────────┐
│ User Input         │
├────────────────────┤
│ • Curriculum       │
│   selectors        │
│ • OR free text     │
│ • Age input        │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Backend (Python)   │
├────────────────────┤
│ 1. Generate        │
│    embedding       │
│ 2. Search FAISS    │
│ 3. Score with LLM  │
│ 4. Rank results    │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Display Results    │
└────────────────────┘
```

#### Deployment Options

**Option A: Streamlit Cloud**
- Current setup, works as-is
- Problem: Large dependencies (FAISS, transformers)
- May hit memory limits on free tier

**Option B: Traditional Cloud (Recommended)**
- **AWS EC2 / GCP Compute**: 
  - Deploy as Docker container
  - t3.medium ($30/mo) should suffice
  - Set up with FastAPI backend + Streamlit/React frontend
- **Railway.app / Render.com**: 
  - Easier than AWS, similar pricing
  - Direct GitHub deployment
  - $20-40/mo for adequate resources

**Option C: Serverless (Advanced)**
- Use AWS Lambda + API Gateway
- Store FAISS index in S3
- Cheaper for low usage, but complex setup

## 🚀 Recommended Roadmap

### Phase 1: Validate Tier 1 (1-2 weeks)

**Week 1:**
1. ✅ Run pre-computation script
   ```bash
   python precompute_curriculum_recommendations.py
   ```
2. ✅ Test `flipper_tier1_lightweight.py` locally
   ```bash
   streamlit run flipper_tier1_lightweight.py
   ```
3. Deploy to Streamlit Cloud
4. Share with 5-10 beta testers (teachers you know)

**Week 2:**
- Gather feedback
- Iterate on UI
- Decide if this meets user needs

**Decision Point**: If Tier 1 provides 80% of value, you may not need Tier 2!

### Phase 2: Polish Tier 1 (2-4 weeks)

**If sticking with Streamlit:**
- Custom CSS for branding
- Add filtering/sorting options
- Improve video cards (add preview, descriptions)

**If moving to proper website:**
- Hire Upwork freelancer ($200-500) to convert to Next.js
- Or learn Next.js yourself (2 weeks with tutorials)
- Deploy to Vercel (free)

### Phase 3: Build Tier 2 (4-6 weeks)

Only if user research shows demand for free-text search.

**Technical Tasks:**
1. Refactor `flipper.py` to separate frontend/backend
2. Add user authentication (Streamlit auth or Auth0)
3. Implement usage limits (queries per user)
4. Set up payment (Stripe for subscriptions)
5. Deploy to cloud with proper monitoring

**Non-Technical Tasks:**
1. Pricing strategy
2. Marketing website
3. Terms of Service / Privacy Policy
4. Support system

### Phase 4: Mobile App (Optional, 8-12 weeks)

Only after web version is proven.

**Options:**
- Flutter (cross-platform: Android + iOS)
- React Native
- Or hire mobile developer on Upwork

## 💰 Cost Analysis

### Tier 1 Costs

**Development (One-time):**
- Pre-computation run: ~$5-20 in OpenAI API calls
- Your time: 1-2 weeks

**Monthly Operating Costs:**

| Approach | Hosting | Domain | Total/mo |
|----------|---------|--------|----------|
| Streamlit Cloud | FREE | - | $0 |
| Netlify/Vercel | FREE | $12 | $12 |
| Airtable+Softr | $49 | $12 | $61 |

**Scaling**: Can handle 10,000s of users at same price

### Tier 2 Costs

**Monthly Operating Costs:**

| Component | Cost/mo | Notes |
|-----------|---------|-------|
| Server (e.g., EC2 t3.medium) | $30 | For FAISS + app |
| OpenAI API | $10-200 | Depends on usage |
| Database (PostgreSQL) | $15 | For user data |
| Domain + SSL | $12 | - |
| Monitoring (optional) | $10 | DataDog/Sentry |
| **Total** | **$77-267** | Per 100-1000 users |

**Scaling**: Each 1000 active users ~$50-100/mo additional

## 🎨 Tier 1 Web Dev Crash Course

Since you have no web dev experience, here's the **fastest path** to a professional-looking Tier 1 service:

### Absolute Easiest: Streamlit Cloud (0 web dev required)

```bash
# 1. Create requirements.txt
echo "streamlit
pandas" > requirements_tier1.txt

# 2. Push to GitHub
git init
git add flipper_tier1_lightweight.py precomputed_recommendations.csv requirements_tier1.txt
git commit -m "Tier 1 lightweight curriculum guide"
git push

# 3. Go to share.streamlit.io
# - Connect GitHub account
# - Select repo
# - Deploy
# - Get URL like: flipper.streamlit.app
```

**Customization:**
```python
# Add to flipper_tier1_lightweight.py for custom styling

st.markdown("""
<style>
    .main {
        background-color: #f0f2f6;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)
```

### Next Level: Static HTML Site (1-2 days learning)

**Option 1: Use a template**

1. Download free template:
   - [HTML5 UP](https://html5up.net/) - Beautiful, free templates
   - Pick one with a table/data display
   
2. Replace their data with your CSV:
   ```javascript
   // Load CSV and display
   fetch('precomputed_recommendations.csv')
     .then(response => response.text())
     .then(data => {
       // Parse and display
       // Use library like PapaParse
     });
   ```

3. Deploy to Netlify:
   - Drag & drop your folder to netlify.com
   - Done!

**Option 2: Use AI to convert**

Seriously, use Claude/ChatGPT:
```
Prompt: "Convert this Streamlit app to a static HTML/CSS/JavaScript 
website. Make it mobile-responsive using Bootstrap."

[Paste flipper_tier1_lightweight.py code]
```

Then iterate with AI to fix issues.

## 🔒 Security & Privacy Considerations

### Tier 1
- ✅ No user data collected
- ✅ No authentication needed
- ✅ No sensitive API keys
- ⚠️ Consider: Rate limiting to prevent scraping

### Tier 2
- ⚠️ User accounts = GDPR compliance needed
- ⚠️ Protect OpenAI API key (use environment variables)
- ⚠️ Rate limit queries (prevent abuse)
- ⚠️ Log user searches (privacy policy required)

## ❓ Potential Issues & Solutions

### Issue 1: CSV file too large for Streamlit Cloud
**Solution**: 
- Compress CSV (gzip)
- Or store in GitHub LFS
- Or use SQLite database instead

### Issue 2: Pre-computed recommendations get stale
**Solution**:
- Re-run precomputation monthly
- Automate with GitHub Actions
```yaml
# .github/workflows/update-recommendations.yml
name: Update Recommendations
on:
  schedule:
    - cron: '0 0 1 * *'  # Monthly
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: python precompute_curriculum_recommendations.py
      - run: git commit -am "Update recommendations"
      - run: git push
```

### Issue 3: Users want videos not in curriculum
**Solution**: This is what Tier 2 is for! Clear upsell opportunity.

### Issue 4: Need analytics (which topics are popular?)
**Solution**: 
- Tier 1: Use Google Analytics (add to HTML)
- Tier 2: Log searches to database, build dashboard

## 🎓 Learning Resources

### For Tier 1 Static Website
- [HTML/CSS Basics](https://www.freecodecamp.org/) - Free, 5-10 hours
- [JavaScript for beginners](https://javascript.info/) - Free
- [Netlify Deploy Tutorial](https://www.youtube.com/watch?v=bjVUqvcCnxM) - 10 min

### For Tier 2 Full Stack
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/) - Python backend
- [React Basics](https://react.dev/learn) - Modern frontend
- [Docker for beginners](https://docker-curriculum.com/) - Deployment

### For Mobile App
- [Flutter for beginners](https://docs.flutter.dev/get-started/codelab) - 2-3 hours
- [React Native](https://reactnative.dev/docs/tutorial) - Alternative

## 🎯 My Recommendation

Based on your situation (no web dev experience, quality checking nearly done):

**START WITH:**
1. ✅ Run pre-computation script this week
2. ✅ Deploy Tier 1 to Streamlit Cloud (2 hours)
3. ✅ Get 10-20 teacher beta testers
4. ✅ Gather feedback for 2-4 weeks

**THEN DECIDE:**
- If users love it: Invest in professional web design ($500) or learn Next.js
- If users need free-text search: Build Tier 2
- If lukewarm: Pivot based on feedback

**DON'T:**
- ❌ Build Tier 2 first (overbuilding)
- ❌ Try to learn Flutter right away (too much)
- ❌ Pay for expensive hosting before validating users want this

The beauty of Tier 1 is you can have it live **THIS WEEK** with zero cost and validate your entire concept. Then invest time/money based on real user feedback.

## 📞 Next Steps

Ready to start? Here's your checklist:

- [ ] Run `python precompute_curriculum_recommendations.py`
- [ ] Test `streamlit run flipper_tier1_lightweight.py` locally
- [ ] Create GitHub repo
- [ ] Deploy to Streamlit Cloud
- [ ] Share with 5 teachers for feedback
- [ ] Review feedback and decide next phase

Questions? Issues? Let me know and I'll help you through it!
