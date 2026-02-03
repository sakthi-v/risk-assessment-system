@echo off
echo ================================================================================
echo           LAUNCH RAG APP TO ADD NEW DOCUMENTS
echo ================================================================================
echo.
echo This will open the RAG app where you can:
echo   - View your existing 13 documents
echo   - Upload your terminate and transfer forms
echo   - Add them to the knowledge base
echo.
echo ================================================================================
echo.

cd /d "%~dp0"

echo Starting Streamlit app...
echo.
echo The app will open in your browser automatically.
echo.
echo INSTRUCTIONS:
echo 1. Enter your Gemini API key in the sidebar
echo 2. Scroll to "Upload Documents" section
echo 3. Click "Choose files" and select your 2 forms
echo 4. Click "Process & Save Documents"
echo 5. Done! Your knowledge base will be updated
echo.
echo ================================================================================
echo.

streamlit run phase1_rag_app.py

pause
