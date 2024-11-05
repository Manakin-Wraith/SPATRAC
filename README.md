## SPATRAC Inventory Management System

This system is designed to manage inventory tracking, from delivery to processing, with an integrated authentication system for user access control. It utilizes Python with libraries like Pandas, PySimpleGUI, FPDF, barcode, and a custom authentication module.

### Features:

* **Product Management:**
    * Search and select products from loaded CSV data files.
    * Record product deliveries with details like quantity, supplier batch, sell-by date, and temperature logs.
    * Managers can approve and process delivered products, updating their status and location.
* **Departmentalization:**
    * Products are categorized by department (Butchery, Bakery, HMR).
    * Department-specific views are available for processing and managing products within each department.
    * Managers can only process products within their assigned department, except for Delivery Managers who have global access.
* **Inventory Overview:**
    * View the current inventory status, including product details, quantity, and status.
    * View detailed product information including handling history and temperature logs.
    * Generate barcodes for individual products based on batch/lot and supplier batch numbers.
    * Save generated barcodes as PNG images.
* **Reporting:**
    * Generate traceability reports showing product journey and handling information.
    * Generate inventory summary reports by department.
    * Generate temperature log reports.
    * Save reports as PDF or CSV files.
* **Authentication & Authorization:**
    * User authentication with username and password.
    * Role-based access control (Manager, other roles can be added).
    * Managers can only approve/process products within their assigned department.
    * Delivery Managers have access to all departments.


### Usage:

1. **Data Loading:**
   The system loads product data from CSV files specified in the `file_paths` variable within `main.py`.  The CSV files must use semicolon (`;`) as the delimiter and have specific header names (see `required_columns` in `load_data` function).
2. **Authentication:** Upon startup, a login window prompts for username and password.  Predefined user accounts are created in the `create_gui` function. Modify `auth_system.py` to manage users and roles.
3. **Product Receiving:** Use the "Product Management" tab to search for products, enter delivery details, and record temperature information.  The "Receive Product" button creates a new inventory entry.
4. **Product Approval and Processing:** Managers can use the "Inventory" tab to select delivered products and click "Process Selected" to update their status and location.  This action requires manager authorization within the specified department.
5. **Reporting:** Use the "Reports" tab to generate and save reports for specified date ranges.
6. **Inventory Management:** The "Inventory" tab provides an overview of all products in the system. Use "View Details" to access complete information about a selected product.
7. **Barcode Generation:** Select a product in the "Inventory" tab and click "Generate Barcode" to create and display a barcode. The "Save Barcode" button allows saving the barcode as a PNG file.


### Code Structure:

* `main.py`: Contains the main application logic, GUI setup, and event handling.
* `auth_system.py`: Defines the `AuthSystem` class and `User` class, handling user authentication and authorization.
* `data` directory: Ideally, this directory contains your CSV data files. You'll likely need to create this directory and add your data files.

### Dependencies:

* Python 3
* Pandas
* PySimpleGUI
* fpdf
* python-barcode
* Pillow (PIL)

Install dependencies using `pip install pandas PySimpleGUI fpdf python-barcode Pillow`.

## Support

For support, feature requests, or bug reports, please contact:
[Your Support Contact Information]

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

MIT License

© [Gerhard Mostert/Celebration House Entertainment CC.] [2024]. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction for personal, educational, or non-commercial use, including without limitation the rights to use, copy, modify, merge, publish, and distribute copies of the Software, subject to the following conditions:

1. The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

2. Commercial use of the Software, including but not limited to using the Software as part of a business offering, for generating revenue, or within a commercial product, requires a separate commercial license agreement with [Gerhard Mostert/Celebration House Entertainment CC.].

3. Any distribution or modification of the Software for commercial purposes must be done under a commercial license obtained from [Gerhard Mostert/Celebration House Entertainment CC.]. For inquiries regarding commercial licensing, please contact [Your Contact Information].

4. Any use of trademarks, logos, or branding associated with the Software requires explicit permission from [Gerhard Mostert/Celebration House Entertainment CC.].

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Additional Terms:
- This license does not grant any rights to use the Software for commercial purposes without a separate commercial license.
- [Add any additional proprietary claims, trademarks, or specific terms here.]

For commercial licensing inquiries, contact: [Your Contact Information]


## Acknowledgments

- This project was developed using [PySimpleGUI](https://pysimplegui.readthedocs.io/), [Pandas](https://pandas.pydata.org/), and [python-barcode](https://github.com/WhyNotHugo/python-barcode).

\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

```markdown
# SPATRAC Inventory Management System

SPATRAC is a Python-based inventory management system designed for businesses with distinct departments (e.g., Butchery, Bakery, HMR). It streamlines the process of receiving, processing, and tracking inventory, including ingredient usage in recipes.


## Features

* **User Authentication and Authorization:** Secure login with role-based access control (Delivery Manager, Department Manager).
* **Product Receiving:**  Delivery Managers can easily log incoming products with details like quantity, supplier batch, and sell-by date.  Optional temperature logging is supported.
* **Departmentalized Inventory Management:** Each department has its own view of inventory, allowing managers to process products and track stock levels within their area.
* **Recipe Management:**  Department managers can link processed ingredients to final products based on defined recipes, automatically deducting ingredient quantities from inventory.
* **Reporting (Future Enhancement):** Planned features include generating traceability reports, inventory summaries, and temperature logs.


## Installation

1. **Prerequisites:**  Ensure you have Python 3 installed along with the following libraries:
    ```bash
    pip install pandas PySimpleGUI sqlite3 barcode Pillow
    ```
2. **Database Setup:**
    * Run the `main.py` script. This will create the SQLite database file (`spatrac.db`) and the necessary tables if they don't already exist.  
    * You'll need to populate the database with your product and recipe data.  See the "Data Loading" section below.
3. **Configuration:**
   * Update the filepaths in `main.py` to point to your CSV files containing product and recipe information. (See Data Loading below)


## Data Loading

SPATRAC uses CSV files to initially populate the product and recipe information.  You'll need to create these CSV files in the correct format:

**`products.csv`:**
```
product_code,product_description,supplier_product_code,supplier_id,department_id
P001,Beef,BEEF-001,1,1,  
P002,Chicken,CHIC-002,2,1
...
```
* `product_code`: Your internal product code.
* `product_description`: Description of the product.
* `supplier_product_code`: Supplier's product code.
* `supplier_id`: ID of the supplier from the Suppliers table.
* `department_id`: ID of the department from the Departments table.


**`recipes.csv`:** (Same as "DEPARTMENTS - RECIPES - ALL DEPT..csv" but needs proper formatting!)
```
department_id,final_product_name,ingredient_product_code,recipe_quantity
1,Burger,P001,0.5
1,Burger,P003,0.1
...
```
* `department_id`:  ID of the department.
* `final_product_name`: Name of the final product (e.g., "Burger").
* `ingredient_product_code`: Product code of the ingredient.
* `recipe_quantity`:  Quantity of the ingredient used in the recipe.

*NOTE:* The first time you run the application, the `Suppliers` and `Departments` tables will be empty, so you might need to insert data into these tables using a database tool before loading products.  I suggest adding error handling or a setup wizard within the app for future improvements.


## Usage

1. **Login:** Run `main.py`. The login window will appear. Enter your username and password.
2. **Receiving (Delivery Manager):** If you are a Delivery Manager, you will be taken to the Receiving Window.  Enter the product details and click "Receive Product" to log incoming deliveries.
3. **Department Management (Department Manager):**  Department Managers will be redirected to their specific department window.  Here they can:
    * View the current inventory for their department.
    * Select products to process and click "Process Selected."
    * View recipes and link processed ingredients to final products using the "Link Ingredients" section.  This automatically deducts the used ingredients from inventory.



## Troubleshooting

* **Database Errors:** If you encounter any database-related issues, check the `spatrac.db` file and ensure it has been created correctly.  Verify the data in the CSV files matches the expected format.
* **UI Issues:** If the UI is not displaying correctly, make sure you have the required PySimpleGUI version installed.

## Future Enhancements

* **Robust Reporting:** Generate various reports (traceability, inventory summary, temperature logs).
* **Advanced Recipe Management:**  More complex recipe features (scaling, substitutions, etc.).
* **Improved Data Loading:**  Implement a more user-friendly way to import and manage product and recipe data (e.g., through the UI).
* **Enhanced UI/UX:**  Improve the overall user interface and experience based on user feedback.
* **User Management:**  Allow creating and managing users through the UI.

## Contributing

Contributions are welcome!  Feel free to submit bug reports, feature requests, or pull requests.

## License

[Specify your license here (e.g., MIT License)]
```


This README provides a much more complete guide for users and developers working with the SPATRAC system.  Remember to customize it further with any specific instructions or details relevant to your environment and users.