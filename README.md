# AI Risk Assessment System - Setup Guide

## 📋 Overview
Multi-agent AI system for automated risk assessment using CrewAI, RAG, and Google Gemini. Supports TREAT, ACCEPT, TRANSFER, and TERMINATE workflows with intelligent follow-up tracking.

---

## 🚀 Quick Start Guide

### **Step 1: Install Python**
- Download Python 3.9 or higher from: https://www.python.org/downloads/
- During installation, check "Add Python to PATH"
- Verify installation: `python --version`

### **Step 2: Install Dependencies**
Open Command Prompt in project folder and run:
```bash
pip install -r requirements.txt
```

### **Step 3: Get Google Gemini API Key**
1. Go to: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy your API key

### **Step 4: Configure API Keys**
Create a file named `.env` in the project root folder with:
```
GEMINI_API_KEY_1=your_api_key_here
GEMINI_API_KEY_2=your_second_key_here (optional)
GEMINI_API_KEY_3=your_third_key_here (optional)
```

**Note**: Multiple API keys enable automatic rotation to avoid rate limits.

### **Step 5: Initialize Database**
```bash
python setup_database.py
```

### **Step 6: Run the Application**
```bash
streamlit run main_app.py
```

The application will open in your browser at: http://localhost:8501

---

## 📁 Project Structure

```
project_root/
├── main_app.py                 # Main application
├── phase1_rag_app.py           # RAG knowledge base interface
├── risk_register_page.py       # Risk Register UI
├── followup_page.py            # Follow-up tracking UI
├── requirements.txt            # Python dependencies
├── setup_database.py           # Database initialization
├── .env                        # API keys (create this)
├── database/
│   └── risk_register.db        # SQLite database (auto-created)
├── knowledge_base/             # RAG documents
├── phase2_risk_resolver/       # Core agents and logic
│   ├── agents/                 # AI agents
│   ├── database/               # Database operations
│   ├── tools/                  # RAG tools
│   └── config/                 # Agent configurations
├── templates/                  # Excel templates
├── outputs/                    # Agent outputs
└── sessions/                   # Session files
```

---

## 🎯 Key Features

### **1. Multi-Agent Risk Assessment**
- **Agent 0**: Questionnaire Generator
- **Agent 1**: CIA Impact Analyzer
- **Agent 2**: Risk Quantification
- **Agent 3**: Control Evaluation
- **Agent 4**: Management Decision

### **2. Treatment Workflows**
- **TREAT**: Generate treatment plans with actions
- **ACCEPT**: Document risk acceptance with compensating controls
- **TRANSFER**: Transfer risk to third party
- **TERMINATE**: Terminate risk by removing asset/activity

### **3. Follow-up Tracking**
- Automatic follow-up scheduling (5-7 days based on progress)
- AI re-assessment of control effectiveness
- Progress tracking with completion percentages
- Risk reduction calculation

### **4. Risk Register**
- Centralized risk database
- Filtering and search capabilities
- Export to Excel/JSON
- Full risk lifecycle tracking

---

## 🔧 System Requirements

- **Python**: 3.9 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Disk Space**: 500MB minimum
- **Internet**: Required for Google Gemini API
- **Browser**: Chrome, Firefox, Edge, or Safari

---

## 📊 Usage Workflow

1. **Upload Knowledge Base** (Phase 1 RAG App)
   - Upload your organization's risk templates
   - System learns your methodology

2. **Conduct Risk Assessment** (Main App)
   - Select asset from sample data or enter manually
   - Answer AI-generated questionnaire
   - System runs 5 agents to assess risk

3. **Make Treatment Decision** (Agent 4)
   - Choose: TREAT, ACCEPT, TRANSFER, or TERMINATE
   - System generates appropriate forms/plans

4. **Track Follow-ups** (Follow-up Page)
   - System automatically schedules follow-ups
   - Answer progress questionnaire
   - AI re-assesses risk reduction

5. **Monitor Risks** (Risk Register)
   - View all risks in centralized register
   - Filter by status, decision, owner
   - Export reports

---

## ⚠️ Troubleshooting

### **Issue: "Module not found" error**
**Solution**: Reinstall requirements
```bash
pip install -r requirements.txt --force-reinstall
```

### **Issue: "API key not found" error**
**Solution**: Check .env file exists and has correct format
```
GEMINI_API_KEY_1=your_actual_key_here
```

### **Issue: "Database not found" error**
**Solution**: Initialize database
```bash
python setup_database.py
```

### **Issue: Streamlit won't start**
**Solution**: Check if port 8501 is available
```bash
streamlit run main_app.py --server.port 8502
```

### **Issue: SSL certificate errors**
**Solution**: Update certificates
```bash
pip install --upgrade certifi
```

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the .env file configuration
3. Ensure all dependencies are installed
4. Check Python version (must be 3.9+)

---

## 🔐 Security Notes

- **Never commit .env file** to version control
- Keep API keys confidential
- Database contains sensitive risk data - protect accordingly
- Use HTTPS in production environments

---

## 📝 License & Credits

**Technology Stack**:
- CrewAI (Multi-agent framework)
- LangChain (LLM orchestration)
- Google Gemini (AI model)
- Streamlit (Web interface)
- SQLite (Database)

---

**Version**: 1.0  
**Last Updated**: January 2026
