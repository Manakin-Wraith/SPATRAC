# 2025 SPATRAC Roadmap

## Immediate Tasks (Short-term)

### A. Integrate Audit Schema Logic
1. **Update the SQLite Database Schema**:
   - Define New Tables:
     - Create a products table with fields for:
       - Product Name
       - Final Product Batch Code
       - Production/Preparation Date
       - Sell-By Date
       - Use-By Date
       - Quantity Produced
     - Create an ingredients table with fields for:
       - Ingredient Name
       - Supplier Name
       - Supplier Address
       - Batch Code
       - Receiving Date
       - Country of Origin
   - Create Temperature and Cleaning Records Tables:
     - Design a temperature_logs table to store temperature readings with timestamps.
     - Create a cleaning_records table to log cleaning schedules and details.

2. **Modify Data Entry Forms in the UI**:
   - Audit Data Entry Forms:
     - Update existing product entry forms to include new fields for audit data.
     - Create dedicated forms for entering temperature logs and cleaning records.
   - User Interface Elements:
     - Use PySimpleGUI to create dropdowns, text inputs, and date pickers for ease of data entry.

3. **Implement Data Validation**:
   - Validation Logic:
     - Ensure all required fields are filled out before submission.
     - Validate date formats and ensure numerical fields only accept valid numbers.
   - User Feedback:
     - Display error messages for invalid entries and confirmations for successful submissions.

### B. Enhance Reporting Functionality
1. **Develop New Reporting Functions**:
   - Traceability Reports:
     - Create functions that query the database for audit-related information and format it into a report.
   - Export Options:
     - Implement functionality to export reports in PDF and CSV formats using FPDF and pandas.

2. **User-Friendly Reporting Interface**:
   - UI Elements for Reports:
     - Add buttons or menu options in the UI for users to generate and download reports easily.

### C. User Interface Improvements
1. **Refine the UI for Better Usability**:
   - UI Layout:
     - Review and redesign existing layouts to make audit-related features easily accessible.
   - Consistency:
     - Ensure consistent styling (fonts, colors) across all UI components.

2. **Implement User Feedback Mechanisms**:
   - Notifications:
     - Add success notifications for actions such as data submissions or report generations.
   - Error Handling:
     - Provide clear error messages when user input fails validation.

## 2. UI and UX Brainstorm Session
- Schedule a Session:
  - Gather team members to discuss potential UI and UX enhancements.
  - Focus on user flow, accessibility, and visual appeal.

- Key Discussion Points:
  - Analyze current user pain points and gather feedback on existing UI.
  - Explore design inspirations and best practices for inventory management systems.
  - Consider implementing modern UI frameworks or libraries for improved aesthetics.

## Conclusion
This roadmap serves as a guide for the upcoming improvements and integrations into the SPATRAC project. It will be updated as we progress through the tasks and gather feedback.
