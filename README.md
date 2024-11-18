# SPATRAC - SaaS Product Tracking & Recipe Control System

SPATRAC is a comprehensive Python-based SaaS inventory management system designed for businesses that need robust product tracking, recipe management, and delivery processing capabilities. Built with a focus on usability and efficiency, SPATRAC provides a modern interface for managing inventory across different departments.

## Features

### 1. Product Management
- Product code and supplier code tracking
- Department-specific inventory management
- Barcode generation and scanning
- Detailed product information tracking
- Supplier batch and sell-by date monitoring

### 2. Recipe Management
- Create and edit recipes
- Manage recipe ingredients with quantities
- Department-specific recipe organization
- CSV import/export capabilities
- Ingredient-product matching system

### 3. Inventory Control
- Real-time inventory tracking
- Department-based stock management
- Received product logging
- Stock level monitoring
- Automated inventory updates

### 4. Reporting System
- Comprehensive inventory reports
- Traceability reporting
- Temperature logging
- PDF and CSV export options
- Professional report formatting

### 5. Security Features
- Role-based access control
- Department-level data segregation
- Secure authentication system
- User activity logging
- Data validation and sanitization

## Technical Stack

- **Frontend**: PySimpleGUI
- **Database**: SQLite
- **Data Processing**: pandas
- **PDF Generation**: FPDF
- **Python Version**: 3.12
- **Environment**: macOS compatible

## Dependencies

PySimpleGUI
pandas
sqlite3
fpdf
pillow

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/SPATRAC_Python.git
```

2. Create and activate a virtual environment:
```bash
python -m venv spar_env
source spar_env/bin/activate  # On Unix/macOS
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

1. Run the application:
```bash
python main.py
```

2. Log in with your credentials:
- Default departments: Butchery, Bakery, HMR
- User roles: Manager, Staff

3. Navigate through the tabs:
- Product Management
- Inventory
- Recipes
- Reports

## Database Structure

### Received Products Table
- id (Primary Key)
- product_code
- description
- quantity
- unit
- department
- received_by
- received_date
- supplier_batch
- sell_by_date
- status

## Security

- User authentication through custom AuthSystem
- Department-level data access control
- Secure product and inventory tracking
- Role-based permissions

## Best Practices

1. **Data Entry**:
   - Always scan or enter complete product information
   - Verify supplier batch numbers
   - Check sell-by dates

2. **Inventory Management**:
   - Regular stock counts
   - Prompt received product logging
   - Accurate quantity updates

3. **Recipe Control**:
   - Standardize measurements
   - Regular recipe reviews
   - Ingredient verification

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Authors

- Your Name - *Initial work* - [YourGitHub](https://github.com/yourusername)

## Acknowledgments

- PySimpleGUI team for the excellent GUI framework
- All contributors who have helped shape this project