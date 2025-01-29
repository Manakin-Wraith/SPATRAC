import pandas as pd
import PySimpleGUI as sg
import csv
from fpdf import FPDF
from datetime import datetime
import sqlite3
import json
import base64
import os
import tempfile
import io
from PIL import Image
import barcode
from barcode import Code128
from barcode.writer import ImageWriter
from auth_system import AuthSystem
from database_updates import update_database_schema, migrate_existing_data
from audit_ui import create_audit_tab, handle_audit_events

# Constants
FONT_HEADER = ('Helvetica', 24)
FONT_SUBHEADER = ('Helvetica', 18)
FONT_NORMAL = ('Helvetica', 12)
FONT_SMALL = ('Helvetica', 10)
PAD = (10, 5)
COLORS = {
    'primary': '#1a73e8',
    'secondary': '#f1f3f4',
    'text': '#202124',
    'success': '#0f9d58',
    'warning': '#f4b400',
    'error': '#d93025',
    'danger': '#d93025'  # Using the same color as error for danger
}

# Load the data
def load_data(file_paths):
    dfs = []
    required_columns = [
        "Supp. Cd.", "Supplier Name", "Sub-Department", 
        "Supplier Product Code", "Product Code", "Product Description"
    ]
    
    for file_path in file_paths:
        try:
            print(f"Loading data from {file_path}")
            df = pd.read_csv(file_path, encoding='iso-8859-1', sep=';')
            df.columns = df.iloc[0]
            df = df.iloc[1:]  # Remove the first row since it's now the header
            print(f"Loaded data from {file_path} with {len(df)} rows")
            
            # Check if all required columns are present
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                print(f"Warning: Missing required columns in {file_path}: {missing_cols}")
                continue
                
            # Select only required columns and add Status column
            df = df[required_columns].copy()
            df['Status'] = 'Active'  # Add Status column with default value
            df['Department'] = file_path.split()[0].lower()
            df['unique_id'] = [f"row_{i}" for i in range(len(df))]
            df.set_index('unique_id', inplace=True, drop=False)
            
            dfs.append(df)
            print(f"Added data from {file_path} to the list of dataframes")
        except FileNotFoundError:
            print(f"Error: File {file_path} not found")
        except pd.errors.EmptyDataError:
            print(f"Error: File {file_path} is empty")
        except pd.errors.ParserError as e:
            print(f"Error parsing file {file_path}: {str(e)}")
    
    if not dfs:
        print("No valid data files found")
        return pd.DataFrame()
        
    print(f"Concatenating {len(dfs)} dataframes")
    return pd.concat(dfs, ignore_index=True)

# Sub-department mapping
SUB_DEPT_MAPPING = {
    '201': ('CALLC', 'BUTCHERY'),
    '202': ('CBEEF', 'BEEF'),
    '203': ('CCHIC', 'BUTCHERY CHICKENS'),
    '204': ('CLAMB', 'LAMB'),
    '205': ('CMUTT', 'MUTTON'),
    '206': ('COFFL', 'ALL OFFAL'),
    '207': ('CPORK', 'PORK'),
    '208': ('CTURK', 'BUTCHERY TURKEY'),
    '209': ('CVEAL', 'VEAL'),
    '210': ('CBING', 'INGREDIENTS'),
    '211': ('CALPAC', 'BUTCHERY PACKAGING')
}

# Product operations
def deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date, auth_system, window):
    """Deliver a product to inventory."""
    try:
        # Get product details from the database
        print(f"Retrieving product details for {product_code}")
        product = df[df['Product Code'] == product_code].iloc[0].to_dict()
        print(f"Product details: {product}")
        
        # Create a new product entry
        print(f"Creating a new product entry with product code {product_code}")
        new_product = {
            'Product Code': product_code,
            'Product Description': product.get('Product Description', ''),
            'Quantity': quantity,
            'Unit': unit,
            'Supplier Batch No': supplier_batch,
            'Sell By Date': sell_by_date,
            'Temperature Log': [],  # Initialize empty temperature log
            'Handling History': []  # Initialize empty handling history
        }
        print(f"New product entry: {new_product}")
        
        # Record temperature before adding to inventory
        print(f"Recording temperature for new product entry")
        temp_log = record_temperature_popup()
        if temp_log is None:
            print(f"Temperature recording cancelled. Product not received.")
            sg.popup_error('Temperature recording cancelled. Product not received.', font=FONT_NORMAL)
            return None
        print(f"Temperature recording successful: {temp_log}")
        new_product['Temperature Log'].append(temp_log)
        
        # Add the product to inventory
        print(f"Adding the product to inventory")
        if add_received_product(new_product, auth_system, window):
            print(f"Product added successfully")
            return new_product
        print(f"Product not added to inventory")
        return None
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sg.popup_error('Error', f'Failed to deliver product: {str(e)}', font=FONT_NORMAL)
        return None

def approve_delivery(product, auth_system):
    current_user = auth_system.get_current_user_info()
    approval_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"Approving delivery for product: {product}")
    product['Status'] = 'Delivery Approved'
    print(f"Setting status to 'Delivery Approved'")
    
    product['Delivery Approved By'] = current_user["username"]
    print(f"Delivery approved by: {current_user['username']}")
    
    product['Delivery Approval Date'] = approval_date
    print(f"Approval date set to: {approval_date}")
    
    product['Handling History'] += f"\nDelivery approved at {approval_date} by {current_user['username']}"
    print(f"Updated handling history: {product['Handling History']}")
    
    print(f"Final product details: {product}")
    return product

def process_product(product, auth_system):
    current_user = auth_system.get_current_user_info()
    processing_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Processing product: {product}")
    
    # Get temperature reading
    temp_reading = record_temperature_popup()
    if temp_reading is None:  # User cancelled temperature recording
        print(f"Temperature recording cancelled. Product not processed.")
        return None
        
    print(f"Temperature recording successful: {temp_reading}")
    
    # Update product status and details
    print(f"Updating product status to 'Processed'")
    product['Status'] = 'Processed'  # This will be used by update_product_in_database
    print(f"Setting Processing Date to {processing_date}")
    product['Processing Date'] = processing_date
    print(f"Setting Processed By to {current_user['username']}")
    product['Processed By'] = current_user['username']
    print(f"Setting Current Location to {product['Department']} Processing")
    product['Current Location'] = f"{product['Department']} Processing"
    
    # Create received info using Delivery Date
    received_info = (f"Originally received on {product.get('Delivery Date', 'Unknown Date')} "
                    f"by {product.get('Received By', 'Unknown')}")
    
    # Add detailed handling history with temperature
    if not product.get('Handling History'):
        print(f"Initialising Handling History with received info")
        product['Handling History'] = received_info
    else:
        print(f"Updating Handling History with processing info")
    product['Handling History'] += (f"\nProcessed at {processing_date} "
                                  f"by {current_user['username']} in {product['Department']}\n"
                                  f"Temperature reading: {temp_reading}\n"
                                  f"Product journey: {received_info} → Processed")
    
    # Update temperature log
    if not product.get('Temperature Log'):
        print(f"Initialising Temperature Log")
        product['Temperature Log'] = []
    else:
        print(f"Updating Temperature Log")
    product['Temperature Log'].append(f"{processing_date}: {temp_reading}")
    
    # Update the product in the database
    print(f"Updating product in the database")
    update_product_in_database(product)
    
    return product

# Barcode generation
def generate_barcode(data):
    print(f"Generating barcode for {data}")
    code128 = barcode.get_barcode_class('code128')
    rv = io.BytesIO()
    print(f"Writing barcode to memory")
    code128(data, writer=ImageWriter()).write(rv)
    print(f"Opening barcode image from memory")
    image = Image.open(rv)
    print(f"Thumbnailing image")
    image.thumbnail((300, 300))
    return image

def generate_product_barcode(product_code, batch_no, sell_by_date):
    """Generate a barcode for a product using Code128 format."""
    try:
        # Add timestamp to create a unique identifier
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        combined_batch = f"{product_code}-{batch_no}-{timestamp}"
        print(f"Generating barcode for {combined_batch}")
        
        # Generate the barcode in memory
        code128 = Code128(combined_batch, writer=ImageWriter())
        print(f"Generated barcode for {combined_batch}")
        
        # Save barcode to BytesIO buffer
        buffer = io.BytesIO()
        code128.write(buffer)
        print(f"Wrote barcode to memory")
        
        # Convert to base64
        barcode_image = base64.b64encode(buffer.getvalue()).decode()
        print(f"Base64 encoded barcode: {barcode_image}")
        
        return {
            'barcode_data': combined_batch,
            'barcode_image': barcode_image
        }
    except Exception as e:
        print(f"Error generating barcode: {str(e)}")
        return None

def add_product_to_inventory(values, auth_system):
    """Add a new product to the inventory database."""
    try:
        current_user = auth_system.get_current_user_info()
        if not current_user:
            print("User not authenticated")
            return False, "User not authenticated"

        # Generate barcode
        print("Generating barcode...")
        barcode_info = generate_product_barcode(
            values['-PRODUCT_CODE-'],
            values['-SUPPLIER_BATCH-'],
            values['-SELL_BY_DATE-']
        )
        
        if not barcode_info:
            print("Failed to generate barcode")
            return False, "Failed to generate barcode"

        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        print("Inserting product into database...")
        print(f"Inserting barcode_data: {barcode_info['barcode_data']}")
        print(f"Inserting barcode_image: {barcode_info['barcode_image']}")
        cursor.execute('''
            INSERT INTO received_products (
                product_code, description, quantity, unit, 
                supplier_batch, sell_by_date, received_date,
                received_by, status, department, handling_history,
                barcode_data, barcode_image, processed_by, processing_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            values['-PRODUCT_CODE-'],
            values['-DESCRIPTION-'],
            values['-QUANTITY-'],
            values['-UNIT-'],
            values['-SUPPLIER_BATCH-'],
            values['-SELL_BY_DATE-'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            current_user['username'],
            'Active',
            current_user['department'],
            f"Product added by {current_user['username']} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            barcode_info['barcode_data'],
            barcode_info['barcode_image'],
            current_user['username'],  # processed_by
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # processing_date
        ))
        
        conn.commit()
        conn.close()
        print("Product added successfully with barcode")
        return True, "Product added successfully with barcode"
        
    except sqlite3.Error as e:
        print(f"Database error: {str(e)}")
        return False, f"Database error: {str(e)}"
    except Exception as e:
        print(f"Error adding product: {str(e)}")
        return False, f"Error adding product: {str(e)}"

def show_database_product_details(product, auth_system):
    """Display detailed product information from the database view."""
    print("Fetching user information...")
    user_info = auth_system.get_current_user_info()
    manager_info = f"Viewed by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Viewed by: N/A"
    
    # Create temporary file for barcode image if available
    print("Checking for barcode image...")
    barcode_image_path = None
    if product.get('barcode_image'):
        try:
            import tempfile
            from PIL import Image
            import io
            import base64
            
            print("Decoding barcode image...")
            image_data = base64.b64decode(product['barcode_image'])
            image = Image.open(io.BytesIO(image_data))
            
            print("Creating temporary file for barcode image...")
            temp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            image.save(temp.name, format='PNG')
            temp.close()
            barcode_image_path = temp.name
        except Exception as e:
            print(f"Error creating barcode image: {str(e)}")
    
    print("Building window layout...")
    layout = [
        [sg.Text('Database Product Details', font=FONT_HEADER)],
        [sg.Text(manager_info, font=FONT_SMALL)],
        [sg.Text(f"Product Code: {product.get('product_code', 'N/A')}")],
        [sg.Text(f"Description: {product.get('description', 'N/A')}")],
        [sg.Text(f"Quantity: {product.get('quantity', 'N/A')} {product.get('unit', '')}")],
        [sg.Text(f"Department: {product.get('department', 'N/A')}")],
        [sg.Text(f"Status: {product.get('status', 'N/A')}")],
        [sg.Text(f"Supplier Batch: {product.get('supplier_batch', 'N/A')}")],
        [sg.Text(f"Sell by Date: {product.get('sell_by_date', 'N/A')}")],
        [sg.Text(f"Received Date: {product.get('received_date', 'N/A')}")],
        [sg.Text(f"Received By: {product.get('received_by', 'N/A')}")],
    ]
    
    if product.get('barcode_data'):
        print("Adding barcode information to layout...")
        layout.extend([
            [sg.Text('Barcode Information', font=('Helvetica', 10, 'bold'))],
            [sg.Text(f"Barcode Data: {product['barcode_data']}")],
        ])
        if barcode_image_path:
            layout.append([sg.Image(barcode_image_path, size=(300, 100))])
    
    if product.get('processed_by'):
        print("Adding processing information to layout...")
        layout.extend([
            [sg.Text('Processing Information', font=('Helvetica', 10, 'bold'))],
            [sg.Text(f"Processed By: {product['processed_by']}")],
            [sg.Text(f"Processing Date: {product.get('processing_date', 'N/A')}")],
        ])
    
    layout.extend([
        [sg.Text('Handling History:', font=('Helvetica', 10, 'bold'))],
        [sg.Multiline(product.get('handling_history', 'No handling history available'), size=(60, 5), disabled=True)],
        [sg.Text('Temperature Log:', font=('Helvetica', 10, 'bold'))],
        [sg.Multiline('\n'.join(product.get('temperature_log', ['No temperature log available'])), size=(60, 3), disabled=True)],
        [sg.Button('Close')]
    ])
    
    print("Creating details window...")
    details_window = sg.Window('Database Product Details', layout, modal=True, finalize=True)
    
    print("Centering window on screen...")
    details_window.move(details_window.current_location()[0], 0)
    
    print("Entering event loop...")
    while True:
        event, _ = details_window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            print("Close event detected, exiting loop.")
            break
    
    print("Closing details window...")
    details_window.close()
    
    if barcode_image_path:
        print("Cleaning up temporary barcode image file...")
        try:
            import os
            os.unlink(barcode_image_path)
        except Exception as e:
            print(f"Error cleaning up barcode image file: {str(e)}")

# New function for search suggestions
def get_search_suggestions(df, search_term):
    suggestions = df[df['Product Description'].str.contains(search_term, case=False, na=False)]['Product Description'].tolist()
    return suggestions[:10]

# Modified create_gui function
def create_gui(df):
    # Initialize the database
    initialize_database()
    
    auth_system = AuthSystem()
    auth_system.add_user("john", "password123", "Delivery", "Manager")
    auth_system.add_user("jane", "securepass456", "Bakery", "Manager")
    auth_system.add_user("bob", "manager789", "Butchery", "Manager")
    auth_system.add_user("alice", "admin321", "HMR", "Manager")

    sg.theme('LightGrey1')
    sg.set_options(font=FONT_NORMAL)

    while True:
        if not show_login_window(auth_system):
            print("Login failed, exiting...")
            return

        user_info = auth_system.get_current_user_info()
        user_info_text = f"User: {user_info['username']} | Role: {user_info['role']} | Department: {user_info['department']}"

        departments = ['Butchery', 'Bakery', 'HMR']

        layout = [
            [sg.Text('SPATRAC Inventory Management System', font=FONT_HEADER, justification='center', expand_x=True, pad=((0, 0), (20, 20)))],
            [sg.Text(user_info_text, font=FONT_SMALL, justification='right', expand_x=True, pad=((0, 0), (0, 20)))],
            [sg.TabGroup([
                [sg.Tab('Product Management', create_product_management_tab(df, departments)),
                 sg.Tab('Receiving', create_receiving_tab()),
                 sg.Tab('Recipes', create_recipes_tab()),
                 sg.Tab('Reports', create_reports_tab()),
                 create_database_management_tab(),
                 create_audit_tab()]
            ], key='-TABGROUP-', expand_x=True, expand_y=True)],
            [sg.Button('Logout', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Button('Exit', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary']))]
        ]

        window = sg.Window('SPATRAC', layout, finalize=True, resizable=True, size=(1200, 800))
        
        inventory = []

        print("Entering main event loop...")
        while True:
            event, values = window.read(timeout=100)
            if event in (sg.WIN_CLOSED, 'Exit'):
                print("Window closed, exiting...")
                return
            if event == 'Logout':
                auth_system.logout()
                window.close()
                print("Logged out, closing window...")
                break

            print(f"Handling event: {event}")
            handle_product_management_events(event, values, window, df, inventory, auth_system)
            handle_receiving_events(event, values, window, inventory, auth_system)
            handle_recipes_events(event, values, window, df)
            handle_reports_events(event, values, window, inventory, auth_system)  # Added auth_system
            handle_database_management_events(event, values, window, inventory, auth_system)
            if event.startswith('-'):  # Audit-related events start with -
                handle_audit_events(event, values, window, auth_system)

        print("Closing window...")
        window.close()

def create_product_management_tab(df, departments):
    all_product_descriptions = sorted(df['Product Description'].unique().tolist())
    
    print("Creating product management tab layout...")
    return [
        [sg.Frame('Product Selection', [
            [sg.Text('Product Description:', size=(15, 1)),
             sg.Combo(all_product_descriptions, key='-PRODUCT_DESC-', size=(40, 1), enable_events=True)],
            [sg.Text('Search (Optional):', size=(15, 1)),
             sg.Input(key='-SEARCH-', size=(30, 1), enable_events=True),
             sg.Button('Search', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary']))],
            [sg.Listbox(values=[], size=(55, 6), key='-SUGGESTIONS-', enable_events=True, visible=False)],
            [sg.Text('Department', size=(15, 1)), 
             sg.Input(key='-DEPARTMENT-', size=(20, 1), readonly=True, text_color='white', background_color='#64778d')],
            [sg.Text('Product Code', size=(15, 1)), 
             sg.Input(key='-PRODUCT-', size=(20, 1), readonly=True, text_color='white', background_color='#64778d')],
            [sg.Text('Supplier Product', size=(15, 1)), 
             sg.Input(key='-SUPPLIER_PRODUCT-', size=(20, 1), readonly=True, text_color='white', background_color='#64778d')],
            [sg.Text('Quantity', size=(15, 1)),
             sg.Input(key='-QUANTITY-', size=(10, 1)),
             sg.Combo(['unit', 'kg'], default_value='unit', key='-UNIT-', size=(5, 1))],
            [sg.Text('Supplier Batch', size=(15, 1)), sg.Input(key='-SUPPLIER_BATCH-', size=(20, 1))],
            [sg.Text('Sell by Date', size=(15, 1)),
             sg.Input(key='-SELL_BY_DATE-', size=(10, 1), default_text=datetime.now().strftime('%Y-%m-%d')),
             sg.CalendarButton('Select Date', target='-SELL_BY_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['primary']))],
            [sg.Button('Receive Product', key='-DELIVER-', size=(15, 1), button_color=(COLORS['text'], COLORS['primary']))],
        ], relief=sg.RELIEF_SUNKEN, expand_x=True, expand_y=True)]
    ]

def create_receiving_tab():
    print("Creating receiving tab layout...")
    layout = [
        [sg.Text('Receiving Overview', font=FONT_HEADER)],
        [sg.Column([
            [sg.Text('Active Products', font=FONT_SUBHEADER)],
            [sg.Table(values=[],
                      headings=['Product Code', 'Description', 'Quantity', 'Unit', 
                                'Supplier Batch No', 'Sell By Date', 'Received Date', 'Received By'],
                      auto_size_columns=True,
                      display_row_numbers=False,
                      justification='left',
                      num_rows=15,
                      key='-RECEIVING_TABLE-',
                      enable_events=True)],
            [sg.Button('View Details', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Process Selected', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Refresh', button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Button('Delete All', button_color=(COLORS['text'], COLORS['secondary']))]
        ], vertical_alignment='top'),
        sg.Column([
            [sg.Text('Processed Products', font=FONT_SUBHEADER)],
            [sg.Table(values=[],
                      headings=['Product Code', 'Description', 'Quantity', 'Unit', 
                                'Processing Date', 'Processed By', 'Temperature', 'Status'],
                      auto_size_columns=True,
                      display_row_numbers=False,
                      justification='left',
                      num_rows=15,
                      key='-PROCESSED_TABLE-',
                      enable_events=True)],
            [sg.Button('View Processed Details', button_color=(COLORS['text'], COLORS['primary']))]
        ], vertical_alignment='top')]
    ]
    print("Receiving tab layout created successfully.")
    return layout

def create_recipes_tab():
    print("Creating recipes tab layout...")
    layout = [
        [sg.Text("Recipes Management", font=FONT_HEADER)],
        [sg.Frame("Add/Edit Recipe", [
            [sg.Text("Recipe Code:"), sg.Input(key='-RECIPE_CODE-', size=(15, 1)),
             sg.Text("Recipe Name:"), sg.Input(key='-RECIPE_NAME-', size=(30, 1))],
            [sg.Text("Department:"), 
             sg.Combo(['HMR', 'BUTCHERY', 'BAKERY'], key='-RECIPE_DEPT-', size=(15, 1))],
            [sg.Frame("Ingredients", [
                [sg.Text("Ingredient Code:"), sg.Input(key='-ING_CODE-', size=(15, 1)),
                 sg.Text("Quantity:"), sg.Input(key='-ING_QTY-', size=(10, 1))],
                [sg.Button('Add Ingredient', button_color=(COLORS['text'], COLORS['primary'])),
                 sg.Button('Remove Selected', button_color=(COLORS['text'], COLORS['secondary']))],
                [sg.Table(values=[], headings=['Ingredient Code', 'Description', 'Quantity', 'Pack Deliver'],
                         key='-INGREDIENTS_TABLE-', auto_size_columns=True,
                         enable_events=True, num_rows=5)]
            ])],
            [sg.Button('Save Recipe', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Clear', button_color=(COLORS['text'], COLORS['secondary']))]
        ])],
        [sg.Frame("Recipe List", [
            [sg.Table(values=[], 
                     headings=['Recipe Code', 'Recipe Name', 'Department', '# of Ingredients'],
                     key='-RECIPES_TABLE-',
                     auto_size_columns=True,
                     enable_events=True,
                     num_rows=10)]
        ])]
    ]
    print("Recipes tab layout created successfully.")
    print("Layout:", layout)
    return layout

def create_department_window(department, processed_products, final_products):
    print(f"Creating window for department: {department}")
    print(f"Processed products: {processed_products}")
    print(f"Final products: {final_products}")
    layout = [
        [sg.Text(f"{department} Processed Products", font=FONT_SUBHEADER)],
        [sg.Table(values=processed_products,
                  headings=['Product Code', 'Description', 'Quantity', 'Unit'],
                  display_row_numbers=False,
                  auto_size_columns=True,
                  num_rows=10,
                  key='-PROCESSED_TABLE-',
                  enable_events=True)],
        [sg.Text("Matched Final Products", font=FONT_SUBHEADER)],
        [sg.Table(values=[],
                  headings=['Final Product Code', 'Final Product Name', 'Ingredient Code', 'Ingredient Description', 'Required Quantity'],
                  display_row_numbers=False,
                  auto_size_columns=True,
                  num_rows=10,
                  key='-MATCHED_TABLE-')],
        [sg.Button('Match Products', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Close', button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    print("Window layout created successfully.")
    return sg.Window(f"{department} Processing", layout, finalize=True)

def get_search_suggestions(df, search_term):
    print(f"Searching for term: {search_term}")
    matched_descriptions = df['Product Description'].str.contains(search_term, case=False, na=False)
    print(f"Matched descriptions: {matched_descriptions.sum()} found")
    suggestions = df[matched_descriptions]['Product Description'].tolist()
    print(f"Suggestions: {suggestions[:10]}")
    return suggestions[:10]  # Limit to top 10 suggestions

def handle_product_management_events(event, values, window, df, inventory, auth_system):
    """Handle events in the Product Management tab."""
    print(f"Handling event: {event}")
    
    if event == '-DELIVER-':
        print("Event is '-DELIVER-', processing delivery...")
        product_code = values['-PRODUCT-']
        quantity = values['-QUANTITY-']
        unit = values['-UNIT-']
        supplier_batch = values['-SUPPLIER_BATCH-']
        sell_by_date = values['-SELL_BY_DATE-']
        
        if product_code and quantity and supplier_batch and sell_by_date:
            product = deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date, auth_system, window)
            if product is not None:
                barcode_info = generate_product_barcode(product_code, supplier_batch, sell_by_date)
                if barcode_info:
                    product['barcode_data'] = barcode_info['barcode_data']
                    product['barcode_image'] = barcode_info['barcode_image']
                
                inventory.append(product)
                update_inventory_table(window, inventory)
                update_department_tables(window, inventory)
        else:
            sg.popup_error('Please fill in all required fields', font=FONT_NORMAL)
    
    if event == '-SEARCH-':
        print("Event is '-SEARCH-', searching for product...")
        search_term = values['-SEARCH-']
        if search_term:
            suggestions = get_search_suggestions(df, search_term)
            window['-SUGGESTIONS-'].update(values=suggestions, visible=True)
        else:
            window['-SUGGESTIONS-'].update(values=[], visible=False)

    if event == '-SUGGESTIONS-':
        print("Event is '-SUGGESTIONS-', updating product description...")
        if values['-SUGGESTIONS-']:
            selected_product = values['-SUGGESTIONS-'][0]
            window['-PRODUCT_DESC-'].update(value=selected_product)
            window['-SUGGESTIONS-'].update(visible=False)
            product_info = df[df['Product Description'] == selected_product].iloc[0]
            window['-DEPARTMENT-'].update(product_info['Department'])
            window['-PRODUCT-'].update(product_info['Product Code'])
            window['-SUPPLIER_PRODUCT-'].update(product_info['Supplier Product Code'])
    
    if event == '-PRODUCT_DESC-':
        print("Event is '-PRODUCT_DESC-', updating department, product and supplier product codes...")
        selected_product = values['-PRODUCT_DESC-']
        if selected_product:
            product_info = df[df['Product Description'] == selected_product].iloc[0]
            window['-DEPARTMENT-'].update(product_info['Department'])
            window['-PRODUCT-'].update(product_info['Product Code'])
            window['-SUPPLIER_PRODUCT-'].update(product_info['Supplier Product Code'])

    if event == 'Search':
        print("Event is 'Search', searching for product...")
        search_term = values['-SEARCH-']
        if search_term:
            suggestions = get_search_suggestions(df, search_term)
            window['-PRODUCT_DESC-'].update(values=suggestions)
        else:
            all_product_descriptions = sorted(df['Product Description'].unique().tolist())
            window['-PRODUCT_DESC-'].update(values=all_product_descriptions)        

def update_department_tables(window, inventory):
    print("update_department_tables called")
    print(f"Window: {window}")
    print(f"Inventory: {inventory}")
    # Function kept for compatibility but no longer updates department tables
    pass

def handle_receiving_events(event, values, window, inventory, auth_system):
    print(f"Handling event: {event}")
    
    if event == '-RECEIVING_TABLE-':
        print("Event is '-RECEIVING_TABLE-', returning early.")
        return
    
    if event == 'View Details':
        selected_rows = values['-RECEIVING_TABLE-']
        print(f"Selected rows for 'View Details': {selected_rows}")
        if not selected_rows:
            sg.popup('Please select a product to view details', font=FONT_NORMAL)
            print("No product selected for viewing details.")
            return
        
        active_items = [item for item in inventory if item.get('Status') == 'Active']
        print(f"Active items: {active_items}")
        if not active_items or selected_rows[0] >= len(active_items):
            sg.popup('Selected product not found', font=FONT_NORMAL)
            print("Selected product not found in active items.")
            return
            
        selected_product = active_items[selected_rows[0]]
        print(f"Selected product for details: {selected_product}")
        show_product_details(selected_product, auth_system)
    
    elif event == 'View Processed Details':
        selected_rows = values['-PROCESSED_TABLE-']
        print(f"Selected rows for 'View Processed Details': {selected_rows}")
        if not selected_rows:
            sg.popup('Please select a processed product to view details', font=FONT_NORMAL)
            print("No processed product selected for viewing details.")
            return
            
        processed_items = [item for item in inventory if item.get('Status') == 'Processed']
        print(f"Processed items: {processed_items}")
        if not processed_items or selected_rows[0] >= len(processed_items):
            sg.popup('Selected processed product not found', font=FONT_NORMAL)
            print("Selected processed product not found.")
            return
            
        selected_product = processed_items[selected_rows[0]]
        print(f"Selected processed product for details: {selected_product}")
        show_product_details(selected_product, auth_system)
    
    elif event == 'Process Selected':
        selected_rows = values['-RECEIVING_TABLE-']
        print(f"Selected rows for 'Process Selected': {selected_rows}")
        if not selected_rows:
            sg.popup('Please select products to process', font=FONT_NORMAL)
            print("No products selected for processing.")
            return
            
        user_info = auth_system.get_current_user_info()
        print(f"Current user info for Process Selected: {user_info}")
        if not user_info or user_info['role'] != 'Manager':
            sg.popup_error('You are not authorized to process products. Only Managers can process products.', font=FONT_NORMAL)
            print("User not authorized to process products.")
            return
            
        active_items = [item for item in inventory if item.get('Status') == 'Active']
        print(f"Active items: {active_items}")
        if not active_items:
            sg.popup('No active products found', font=FONT_NORMAL)
            print("No active products found.")
            return
            
        selected_products = [active_items[row] for row in selected_rows if row < len(active_items)]
        print(f"Selected products for processing: {selected_products}")
        if not selected_products:
            sg.popup('Selected products not found', font=FONT_NORMAL)
            print("Selected products not found.")
            return
            
        process_selected_products(auth_system, inventory, selected_products, window)
        print("Processed selected products.")
        update_inventory_table(window, inventory)
        update_processed_table(window, inventory)
        print("Updated inventory and processed tables after processing.")
    
    elif event == 'Delete All':
        current_user = auth_system.get_current_user_info()
        print(f"Current user info for Delete All: {current_user}")
        if current_user is None:
            sg.popup_error('Access Denied', 'Please log in to delete products.', font=FONT_NORMAL)
            print("Access denied: No user logged in.")
            return
            
        if current_user['role'] != 'Manager':
            sg.popup_error('Access Denied', 'Only Managers can delete all products.', font=FONT_NORMAL)
            print("Access denied: User is not a manager.")
            return
        
        if sg.popup_yes_no(
            'Confirm Delete All', 
            'This will delete ALL active products from the database.\n'
            'This action cannot be undone.\n\n'
            'Do you want to continue?',
            font=FONT_NORMAL
        ) == 'Yes':
            success, message = delete_all_active_products()
            print(f"Delete all active products result: {success}, message: {message}")
            if success:
                sg.popup('Success', message, font=FONT_NORMAL)
                refresh_display(window, inventory, auth_system)
                print("Refreshed display after deletion.")
            else:
                sg.popup_error('Error', message, font=FONT_NORMAL)
    
    elif event == 'Refresh':
        current_user = auth_system.get_current_user_info()
        print(f"Current user info for Refresh: {current_user}")
        if current_user is None:
            sg.popup_error('Access Denied', 'Please log in to refresh data.', font=FONT_NORMAL)
            print("Access denied: No user logged in.")
            return
        
        if sg.popup_yes_no(
            'Confirm Refresh', 
            'This will refresh unprocessed items from the database.\n'
            'Processed items will not be affected.\n\n'
            'Do you want to continue?',
            font=FONT_NORMAL
        ) == 'Yes':
            refresh_display(window, inventory, auth_system)
            print("Refreshed display after confirmation.")

def department_login_window(auth_system, inventory, selected_rows, main_window):
    """Show department login window for processing products."""
    print("Initializing Department Manager Login window.")
    layout = [
        [sg.Text('Department Manager Login', font=FONT_HEADER)],
        [sg.Text('Please log in to process products', font=FONT_NORMAL)],
        [sg.Text('Username:', size=(15, 1), font=FONT_NORMAL), 
         sg.Input(key='-USERNAME-', font=FONT_NORMAL)],
        [sg.Text('Password:', size=(15, 1), font=FONT_NORMAL), 
         sg.Input(key='-PASSWORD-', password_char='*', font=FONT_NORMAL)],
        [sg.Button('Login', size=(10, 1), button_color=(COLORS['text'], COLORS['primary']), font=FONT_NORMAL),
         sg.Button('Cancel', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary']), font=FONT_NORMAL)]
    ]

    print("Layout created for Department Manager Login window.")
    window = sg.Window('Department Manager Login', layout, finalize=True)
    print("Window initialized and finalized.")

    while True:
        event, values = window.read()
        print(f"Event: {event}, Values: {values}")
        
        if event in (sg.WIN_CLOSED, 'Cancel'):
            print("Cancel or close event detected. Closing window.")
            window.close()
            print("Window closed.")
            return False

        if event == 'Login':
            print("Login button pressed.")
            username = values['-USERNAME-']
            password = values['-PASSWORD-']
            print(f"Attempting login with Username: {username}")

            if auth_system.login(username, password):
                print("Login successful.")
                window.close()
                print("Window closed after successful login.")
                return True
            else:
                print("Login failed. Invalid username or password.")
                sg.popup_error('Invalid username or password', font=FONT_NORMAL)
        window.close()
        return False

def process_selected_products(auth_system, inventory, selected_products, window):
    """
    Process the selected products.
    
    Args:
        auth_system: The authentication system
        inventory: The full inventory list
        selected_products: List of selected product dictionaries
        window: The main window
    """
    user_info = auth_system.get_current_user_info()
    if not user_info:
        print("No user logged in. Aborting product processing.")
        return
        
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Record temperature for each product
    for product in selected_products:
        temp_log = record_temperature_popup()
        if temp_log:
            # Initialize Temperature Log as a list if it doesn't exist or is a string
            if 'Temperature Log' not in product or isinstance(product['Temperature Log'], str):
                print("Initializing Temperature Log for product.")
                product['Temperature Log'] = []
            product['Temperature Log'].append(temp_log)
            print(f"Temperature Log for product: {product['Temperature Log']}")
            
        # Update product status and processing info
        product['Status'] = 'Processed'
        product['Processing Date'] = current_time
        product['Processed By'] = user_info['username']
        print(f"Updated product status and processing info to: {product}")
        
        # Handle Handling History - convert from string to list if needed
        if 'Handling History' not in product:
            print("Initializing Handling History for product.")
            product['Handling History'] = []
        elif isinstance(product['Handling History'], str):
            # If it's a string, convert it to a list with the existing history as the first item
            print("Converting Handling History string to list.")
            product['Handling History'] = [product['Handling History']]
            
        # Add new history entry
        product['Handling History'].append(
            f"Processed on {current_time} by {user_info['username']} ({user_info['role']} - {user_info['department']})"
        )
        print(f"Updated Handling History for product to: {product['Handling History']}")
        
        # Update the database with the processed product information
        update_product_in_database(product)
        print("Updated product in database.")
    
    # Update the display
    update_inventory_table(window, inventory)
    update_processed_table(window, inventory)
    
    sg.popup('Success', f'{len(selected_products)} products processed successfully', font=FONT_NORMAL)

def update_product_in_database(product):
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    print(f"Updating product {product['Product Code']} in database with status: {product['Status']}")
    
    # Convert handling history to string for storage if it's a list
    handling_history = product['Handling History']
    if isinstance(handling_history, list):
        print("Converting Handling History list to string.")
        handling_history = '\n'.join(handling_history)
    
    cursor.execute('''
        UPDATE received_products
        SET status = ?,
            handling_history = ?,
            processed_by = ?,
            processing_date = ?
        WHERE product_code = ? AND supplier_batch = ? AND status = 'Active'
    ''', (
        product['Status'],
        handling_history,
        product['Processed By'],
        product['Processing Date'],
        product['Product Code'],
        product.get('Supplier Batch No', '')
    ))
    
    print("Committing changes to database.")
    conn.commit()
    print("Closing database connection.")
    conn.close()

def handle_department_window(window, processed_products, final_products):
    while True:
        event, values = window.read()
        print(f"Event: {event}, Values: {values}")
        if event in (sg.WIN_CLOSED, 'Close'):
            break
        elif event == 'Match Products':
            print("Match Products button pressed.")
            matched_products = match_products(processed_products, final_products)
            print(f"Matched products: {matched_products}")
            window['-MATCHED_TABLE-'].update(matched_products)
    print("Closing window.")
    window.close()
    print("Window closed.")

def match_products(processed_products, final_products):
    print("Matching products...")
    matched = []
    for processed in processed_products:
        processed_code = processed[0]  # Get the ingredient code
        print(f"Checking ingredient code: {processed_code}")
        # Find all recipes that use this ingredient
        for final_product in final_products:
            print(f"Checking final product: {final_product}")
            if processed_code == final_product[2]:  # Check if ingredient code matches
                print(f"Matched ingredient code: {processed_code} with final product {final_product[0]}")
                # Create a row with all necessary information
                matched.append([
                    final_product[0],  # Final Product Code
                    final_product[1],  # Final Product Name
                    processed_code,    # Ingredient Code
                    processed[1],      # Ingredient Description
                    final_product[4]   # Required Quantity
                ])
    print("Finished matching products.")
    return matched


def handle_recipes_events(event, values, window, df):
    print(f"Handling event: {event}, Values: {values}")
    if event == '__TIMEOUT__':
        print("Timeout event, updating recipes table...")
        update_recipes_table(window)
        return

    if event == 'Add Ingredient':
        ing_code = values['-ING_CODE-']
        ing_qty = values['-ING_QTY-']
        if ing_code and ing_qty:
            # Get ingredient description from the main products dataframe
            print(f"Getting ingredient description for code: {ing_code}")
            ing_desc = df[df['Product Code'] == ing_code]['Description'].iloc[0] if not df[df['Product Code'] == ing_code].empty else 'Unknown'
            current_ingredients = window['-INGREDIENTS_TABLE-'].get()
            current_ingredients.append([ing_code, ing_desc, ing_qty, 'P/KG'])  # Added default Pack Deliver
            print(f"Updating ingredients table with new ingredient: {current_ingredients}")
            window['-INGREDIENTS_TABLE-'].update(current_ingredients)
            window['-ING_CODE-'].update('')
            window['-ING_QTY-'].update('')
    
    elif event == '-RECIPES_TABLE-':
        selected_rows = values['-RECIPES_TABLE-']
        if selected_rows:
            recipe = load_recipe_by_index(selected_rows[0])
            if recipe:
                print(f"Selected recipe: {recipe}")
                window['-RECIPE_CODE-'].update(recipe['code'])
                window['-RECIPE_NAME-'].update(recipe['name'])
                window['-RECIPE_DEPT-'].update(recipe['department'])
                # Update ingredients table with all columns
                ingredients_data = [[ing[0], ing[1], ing[2]] for ing in recipe['ingredients']]
                print(f"Updating ingredients table with: {ingredients_data}")
                window['-INGREDIENTS_TABLE-'].update(ingredients_data)
    
    elif event == 'Save Recipe':
        recipe_code = values['-RECIPE_CODE-']
        recipe_name = values['-RECIPE_NAME-']
        department = values['-RECIPE_DEPT-']
        ingredients = window['-INGREDIENTS_TABLE-'].get()
        
        print(f"Saving recipe with code: {recipe_code}, name: {recipe_name}, department: {department}, ingredients: {ingredients}")
        if recipe_code and recipe_name and department and ingredients:
            recipe = {
                'code': recipe_code,
                'name': recipe_name,
                'department': department,
                'ingredients': [[ing[0], ing[1], ing[2], 'P/KG'] for ing in ingredients]
            }
            save_recipe(recipe)
            update_recipes_table(window)
            # Clear the form
            window['-RECIPE_CODE-'].update('')
            window['-RECIPE_NAME-'].update('')
            window['-RECIPE_DEPT-'].update('')
            window['-INGREDIENTS_TABLE-'].update([])

    elif event == 'Clear':
        print("Clearing the form...")
        window['-RECIPE_CODE-'].update('')
        window['-RECIPE_NAME-'].update('')
        window['-RECIPE_DEPT-'].update('')
        window['-INGREDIENTS_TABLE-'].update([])

    return

def load_recipes_from_csv():
    recipes = {}
    try:
        df = pd.read_csv('DEPARTMENTS - RECIPES - ALL DEPT..csv')
        print(f"Loaded {len(df)} recipes from CSV.")
        
        # Initialize variables for tracking current recipe
        current_dept = None
        current_recipe = None
        current_ingredients = []
        
        for _, row in df.iterrows():
            print(f"Processing row: {row}")
            # If we have a new recipe (non-empty Final Product Code)
            if pd.notna(row['Final Product Code']):
                print(f"New recipe: {row['Final Product Code']}")
                # Save previous recipe if exists
                if current_recipe is not None:
                    print(f"Saving previous recipe: {current_recipe}")
                    if current_dept not in recipes:
                        recipes[current_dept] = []
                    recipes[current_dept].append(current_recipe)
                
                # Start new recipe
                current_dept = row['Department']
                print(f"New department: {current_dept}")
                current_recipe = {
                    'code': str(row['Final Product Code']),
                    'name': row['Final Product Name'],
                    'department': row['Department'],
                    'ingredients': []
                }
                print(f"New recipe: {current_recipe}")
                current_ingredients = []
            
            # Add ingredient to current recipe
            if pd.notna(row['Ingredient Prod Code']):
                print(f"Adding ingredient to recipe: {row['Ingredient Prod Code']}")
                ingredient = [
                    str(row['Ingredient Prod Code']),
                    str(row['Ingredient Description']),
                    str(row['Recipe']) if pd.notna(row['Recipe']) else '0',
                    str(row['Pack Deliver']) if pd.notna(row['Pack Deliver']) else 'P/KG'
                ]
                print(f"Ingredient: {ingredient}")
                current_recipe['ingredients'].append(ingredient)
        
        # Add the last recipe
        if current_recipe is not None:
            print(f"Saving last recipe: {current_recipe}")
            if current_dept not in recipes:
                recipes[current_dept] = []
            recipes[current_dept].append(current_recipe)
            
    except Exception as e:
        print(f"Error loading recipes from CSV: {e}")
        return {}
    
    print(f"Loaded {len(recipes)} recipes.")
    return recipes

def save_recipe(recipe):
    print(f"Loading all recipes...")
    recipes = load_all_recipes()
    department = recipe['department']
    print(f"Working with department: {department}")

    if department not in recipes:
        print(f"Department {department} not found, creating new entry...")
        recipes[department] = []

    # Update existing recipe or add new one
    updated = False
    for i, existing_recipe in enumerate(recipes[department]):
        if existing_recipe['code'] == recipe['code']:
            print(f"Updating existing recipe with code: {recipe['code']}")
            recipes[department][i] = recipe
            updated = True
            break

    if not updated:
        print(f"Adding new recipe with code: {recipe['code']}")
        recipes[department].append(recipe)

    # Convert to DataFrame format
    print(f"Converting recipes to DataFrame format...")
    rows = []
    for dept, dept_recipes in recipes.items():
        for r in dept_recipes:
            first_row = True
            for ing in r['ingredients']:
                rows.append({
                    'Department': dept if first_row else '',
                    'Final Product Code': r['code'] if first_row else '',
                    'Final Product Name': r['name'] if first_row else '',
                    'Ingredient Prod Code': ing[0],
                    'Ingredient Description': ing[1],
                    'Pack Deliver': ing[3],
                    'Weight': ing[2],
                    'Recipe': ing[2]
                })
                first_row = False

    # Save to CSV
    print(f"Saving recipes to CSV file...")
    df = pd.DataFrame(rows)
    df.to_csv('DEPARTMENTS - RECIPES - ALL DEPT..csv', index=False)
    print(f"Recipes saved successfully.")

def load_all_recipes():
    print("Loading all recipes...")
    try:
        recipes = load_recipes_from_csv()
        print(f"Loaded {len(recipes)} recipes.")
        return recipes
    except Exception as e:
        print(f"Error loading recipes: {e}")
        return {}

def load_recipe_by_index(index):
    print("Loading recipe by index...")
    recipes = load_all_recipes()
    all_recipes = []
    for dept_recipes in recipes.values():
        all_recipes.extend(dept_recipes)
    
    print(f"Loaded {len(all_recipes)} recipes.")
    if 0 <= index < len(all_recipes):
        print(f"Returning recipe at index {index}")
        return all_recipes[index]
    print(f"Index {index} out of range, returning None.")
    return None

def update_recipes_table(window):
    print("update_recipes_table called")
    recipes = load_all_recipes()
    print(f"Loaded {len(recipes)} recipes.")
    table_data = []
    for dept_recipes in recipes.values():
        print(f"Processing {len(dept_recipes)} recipes in department {dept_recipes[0]['department']}.")
        for r in dept_recipes:
            print(f"Processing recipe with code: {r['code']}")
            table_data.append([r['code'], r['name'], r['department'], len(r['ingredients'])])
    print(f"Updating recipes table with {len(table_data)} rows.")
    window['-RECIPES_TABLE-'].update(table_data)

def handle_reports_events(event, values, window, inventory, auth_system):
    """Handle events in the Reports tab."""
    print(f"Handling reports event: {event}")
    if event == '-GENERATE_REPORT-':
        try:
            print("Generating report...")
            start_date = datetime.strptime(values['-START_DATE-'], '%Y-%m-%d')
            end_date = datetime.strptime(values['-END_DATE-'], '%Y-%m-%d')
            report_type = values['-REPORT_TYPE-']
            
            # Get raw report data
            report_data = generate_report(inventory, report_type, start_date, end_date, auth_system)
            print(f"Generated report data: {report_data}")
            
            # Format report for display
            formatted_report = format_report_for_display(report_data, report_type, auth_system)
            window['-REPORT_PREVIEW-'].update(formatted_report)
            print("Updated report preview.")
            
            # Store raw data for saving
            window.user_data = {
                'current_report': {
                    'data': report_data,
                    'type': report_type,
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            print("Stored report data.")
            
        except ValueError as e:
            print(f"Error generating report: {str(e)}")
            sg.popup_error(f'Error generating report: {str(e)}', title='Report Generation Error')
            
    elif event == '-SAVE_PDF-':
        try:
            print("Saving report as PDF...")
            if not hasattr(window, 'user_data') or 'current_report' not in window.user_data:
                print("No report data stored.")
                sg.popup_error('Please generate a report first.', title='Export Error')
                return
                
            filename = sg.popup_get_file('Save PDF as:', save_as=True, 
                                       file_types=(("PDF Files", "*.pdf"),),
                                       default_extension='.pdf')
            if filename:
                report_info = window.user_data['current_report']
                save_report_as_pdf(filename, report_info['data'], report_info['type'],
                                 report_info['start_date'], report_info['end_date'],
                                 auth_system)
                print("Report saved successfully!")
                sg.popup('Report saved successfully!', title='Success')
                
        except Exception as e:
            print(f"Error saving PDF: {str(e)}")
            sg.popup_error(f'Error saving PDF: {str(e)}', title='PDF Export Error')
            
    elif event == '-SAVE_CSV-':
        try:
            print("Saving report as CSV...")
            if not hasattr(window, 'user_data') or 'current_report' not in window.user_data:
                print("No report data stored.")
                sg.popup_error('Please generate a report first.', title='Export Error')
                return
                
            filename = sg.popup_get_file('Save CSV as:', save_as=True, 
                                       file_types=(("CSV Files", "*.csv"),),
                                       default_extension='.csv')
            if filename:
                report_info = window.user_data['current_report']
                save_report_as_csv(filename, report_info['data'], report_info['type'],
                                 report_info['start_date'], report_info['end_date'],
                                 auth_system)
                print("Report saved successfully!")
                sg.popup('Report saved successfully!', title='Success')
                
        except Exception as e:
            print(f"Error saving CSV: {str(e)}")
            sg.popup_error(f'Error saving CSV: {str(e)}', title='CSV Export Error')

def generate_report(inventory, report_type, start_date, end_date, auth_system):
    print(f"Generating report of type: {report_type}")
    try:
        if not auth_system or not auth_system.get_current_user_info():
            raise ValueError("User not authenticated")
            
        if report_type == 'Inventory Summary':
            print("Generating inventory summary report")
            return generate_inventory_summary(inventory, start_date, end_date, auth_system)
        elif report_type == 'Traceability Report':
            print("Generating traceability report")
            return generate_traceability_report(inventory, start_date, end_date, auth_system)
        else:
            print(f"Unknown report type: {report_type}")
            raise ValueError(f"Unknown report type: {report_type}")
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        raise Exception(f"Error generating report: {str(e)}")

def update_product_fields(window, product):
    print(f"Updating product fields with product: {product}")
    print("Updating product code...")
    window['-PRODUCT-'].update(product['Product Code'])
    print(f"Updated product code: {product['Product Code']}")
    print("Updating supplier product code...")
    window['-SUPPLIER_PRODUCT-'].update(product['Supplier Product Code'])
    print(f"Updated supplier product code: {product['Supplier Product Code']}")
    print("Updating department...")
    window['-DEPARTMENT-'].update(product['Department'])
    print(f"Updated department: {product['Department']}")

def update_inventory_table(window, inventory):
    """Update the inventory table with active (unprocessed) items."""
    # Filter for active items only
    active_items = [item for item in inventory if item.get('Status') == 'Active']
    
    # Update table with active items
    try:
        window['-RECEIVING_TABLE-'].update(values=[
            [item['Product Code'],
             item['Product Description'],
             item['Quantity'],
             item['Unit'],
             item.get('Supplier Batch No', ''),
             item.get('Sell By Date', ''),
             item.get('Delivery Date', ''),
             item.get('Received By', '')] for item in active_items
        ])
    except (KeyError, AttributeError) as e:
        print(f"Error updating inventory table: {e}")
        pass

def update_processed_table(window, inventory):
    """Update the processed items table."""
    print("Updating processed items table...")
    
    # Filter for processed items only
    processed_items = [item for item in inventory if item.get('Status') == 'Processed']
    print(f"Filtered {len(processed_items)} processed items from inventory.")
    
    # Update table with processed items
    processed_data = [
        [item['Product Code'], 
         item['Product Description'], 
         item['Quantity'], 
         item['Unit'],
         item.get('Supplier Batch No', ''),
         item.get('Sell By Date', ''),
         item.get('Processing Date', ''),
         item.get('Processed By', ''),
         item.get('Status', '')] for item in processed_items
    ]
    print(f"Processed data prepared with {len(processed_data)} entries.")
    
    # Get currently displayed data
    current_data = window['-PROCESSED_TABLE-'].get()
    print(f"Currently displayed data has {len(current_data)} entries.")
    
    # Only update if the data is different
    if current_data != processed_data:
        print("Data has changed, updating table...")
        window['-PROCESSED_TABLE-'].update(processed_data)
        print("Table updated.")
    else:
        print("Data is unchanged, no update needed.")

def refresh_display(window, inventory, auth_system):
    """
    Safely refresh the display without modifying processed product data.
    Only updates the visual representation of data that hasn't been processed.
    """
    print("Refreshing display...")
    
    # Get current user's info
    current_user = auth_system.get_current_user_info()
    if current_user is None:
        print("No user logged in, cannot refresh display.")
        return False
        
    try:
        # Get fresh inventory data for the department
        fresh_inventory = get_department_inventory(current_user['department'])
        if fresh_inventory is None:
            print("No fresh inventory data available.")
            fresh_inventory = []
            
        # Keep track of processed items from current inventory
        processed_items = [item for item in inventory if item.get('Status') == 'Processed']
        print(f"Found {len(processed_items)} processed items in current inventory.")
        
        # Create a new inventory list with both processed and fresh items
        new_inventory = processed_items + fresh_inventory
        print(f"Creating new inventory list with {len(new_inventory)} items.")
        
        # Sort inventory by received date (newest first)
        new_inventory.sort(key=lambda x: datetime.strptime(x.get('Received Date', '1900-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S'), reverse=True)
        print("Sorted inventory by received date.")
        
        # Clear and update the inventory list
        inventory.clear()
        inventory.extend(new_inventory)
        print("Updated inventory list.")
        
        # Update both tables
        update_inventory_table(window, inventory)
        update_processed_table(window, inventory)
        print("Updated both tables.")
        
        return True
        
    except Exception as e:
        sg.popup_error('Database Error', f'Error refreshing data: {str(e)}')
        return False

def show_login_window(auth_system):
    """Show login window and handle authentication."""
    print("Initializing login window...")
    layout = [
        [sg.Text('Login', font=FONT_HEADER)],
        [sg.Text('Please log in to continue', font=FONT_NORMAL)],
        [sg.Text('Username:', size=(15, 1), font=FONT_NORMAL), 
         sg.Input(key='-USERNAME-', font=FONT_NORMAL)],
        [sg.Text('Password:', size=(15, 1), font=FONT_NORMAL), 
         sg.Input(key='-PASSWORD-', password_char='*', font=FONT_NORMAL)],
        [sg.Button('Login', size=(10, 1), button_color=(COLORS['text'], COLORS['primary']), font=FONT_NORMAL),
         sg.Button('Exit', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary']), font=FONT_NORMAL)]
    ]
    
    window = sg.Window('Login', layout, finalize=True)
    print("Login window initialized and finalized.")

    while True:
        event, values = window.read()
        print(f"Event: {event}, Values: {values}")
        
        if event in (sg.WIN_CLOSED, 'Exit'):
            print("Closing window...")
            window.close()
            print("Window closed.")
            return False
            
        if event == 'Login':
            print("Login button pressed.")
            username = values['-USERNAME-']
            password = values['-PASSWORD-']
            print(f"Attempting login with Username: {username}")

            if auth_system.login(username, password):
                print("Login successful, closing window.")
                window.close()
                print("Window closed after successful login.")
                return True
            else:
                print("Login failed, showing error popup.")
                sg.popup_error('Invalid username or password', font=FONT_NORMAL)
                
    print("Exiting event loop, closing window.")
    window.close()
    print("Window closed.")
    return False

def record_temperature_popup():
    """Show temperature recording popup window."""
    print("Initializing temperature recording popup window...")
    
    locations = [
        'Receiving', 'Hot Foods', 'Butchery', 'Bakery', 'Fruit & Veg',
        'Admin', 'Coffee shop', 'Floor', 'Location 9', 'Location 10', 'Location 11'
    ]
    
    layout = [
        [sg.Text('Record Temperature', font=FONT_HEADER)],
        [sg.Text('Temperature (°C):', font=FONT_NORMAL), 
         sg.Input(key='-TEMP-', size=(10, 1), font=FONT_NORMAL)],
        [sg.Text('Location:', font=FONT_NORMAL),
         sg.Combo(locations, default_value=locations[0], key='-LOCATION-', 
                 font=FONT_NORMAL, readonly=True)],
        [sg.Button('Submit', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Cancel', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    
    window = sg.Window('Record Temperature', layout, finalize=True)
    print("Temperature recording popup window initialized and finalized.")
    
    while True:
        event, values = window.read()
        print(f"Event: {event}, Values: {values}")
        
        if event in (sg.WIN_CLOSED, 'Cancel'):
            print("Closing window...")
            window.close()
            print("Window closed.")
            return None
            
        if event == 'Submit':
            print("Submit button pressed.")
            try:
                temp = float(values['-TEMP-'])
                print(f"Entered temperature: {temp}")
                if -50 <= temp <= 100:  # Reasonable temperature range
                    print("Valid temperature entered, closing window.")
                    window.close()
                    print("Window closed after submitting temperature.")
                    return {
                        'temperature': temp,
                        'location': values['-LOCATION-'],
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                else:
                    print("Invalid temperature range, showing error popup.")
                    sg.popup_error('Please enter a valid temperature between -50°C and 100°C', 
                                 font=FONT_NORMAL)
            except ValueError:
                print("Invalid temperature value, showing error popup.")
                sg.popup_error('Please enter a valid number for temperature', 
                             font=FONT_NORMAL)
                
    print("Exiting event loop, closing window.")
    window.close()
    print("Window closed.")
    return None

def generate_and_show_barcode(item):
    """Generate and display a barcode for the given item."""
    # Create a combined identifier combining product info
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    combined_batch = f"{item['Product Code']}-{item['Supplier Batch No']}-{timestamp}"
    
    try:
        print("Generating barcode image...")
        # Generate barcode image
        barcode_data = generate_barcode(combined_batch)
        if not barcode_data:
            print("Failed to generate barcode")
            sg.popup_error('Failed to generate barcode', font=FONT_NORMAL)
            return None
            
        print("Generated barcode image")
        # Create window layout
        layout = [
            [sg.Text('Generated Barcode', font=FONT_HEADER)],
            [sg.Text(f"Product: {item['Product Description']}", font=FONT_NORMAL)],
            [sg.Text(f"Code: {item['Product Code']}", font=FONT_NORMAL)],
            [sg.Text(f"Batch: {item['Supplier Batch No']}", font=FONT_NORMAL)],
            [sg.Image(data=barcode_data, key='-IMAGE-')],
            [sg.Button('Save Barcode', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Close', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['secondary']))]
        ]
        
        window = sg.Window('Barcode', layout, finalize=True)
        print("Window initialized and finalized.")
        
        while True:
            event, values = window.read()
            print(f"Event: {event}, Values: {values}")
            if event in (sg.WIN_CLOSED, 'Close'):
                print("Closing window...")
                window.close()
                print("Window closed.")
                return None
                
            if event == 'Save Barcode':
                print("Save Barcode button pressed.")
                save_path = sg.popup_get_file(
                    'Save Barcode As...', 
                    save_as=True, 
                    default_extension='.png',
                    file_types=(('PNG Files', '*.png'),),
                    font=FONT_NORMAL
                )
                if save_path:
                    print("Save as location selected, saving barcode...")
                    try:
                        save_barcode(barcode_data, item)
                        print("Barcode saved successfully.")
                        sg.popup('Barcode saved successfully!', font=FONT_NORMAL)
                    except Exception as e:
                        print(f"Error saving barcode: {str(e)}")
                        sg.popup_error(f'Error saving barcode: {str(e)}', font=FONT_NORMAL)
                        
        print("Exiting event loop, closing window.")
        window.close()
        print("Window closed.")
        return None
        
    except Exception as e:
        print(f"Error generating barcode: {str(e)}")
        sg.popup_error(f'Error generating barcode: {str(e)}', font=FONT_NORMAL)
        return None

def save_barcode(barcode_data, item):
    """Save the barcode image and update the database with barcode information."""
    try:
        print("Save Barcode called...")
        # Generate a unique filename based on item details
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_filename = f"barcode_{item['Product Code']}_{timestamp}.png"
        
        # Get save location from user
        save_path = sg.popup_get_file(
            'Save Barcode As...', 
            save_as=True,
            default_extension='.png',
            default_path=default_filename,
            file_types=(('PNG Files', '*.png'),),
            font=FONT_NORMAL
        )
        
        if not save_path:
            print("No save path selected, returning False")
            return False
            
        # Ensure .png extension
        if not save_path.lower().endswith('.png'):
            save_path += '.png'
            print(f"Added .png extension to filename, now {save_path}")
            
        # Save the barcode image
        with open(save_path, 'wb') as f:
            f.write(barcode_data)
            print(f"Barcode image saved to {save_path}")
            
        # Convert barcode data to base64 for database storage
        barcode_base64 = base64.b64encode(barcode_data).decode()
        print("Barcode data converted to base64")
        
        # Generate tracking ID
        tracking_id = f"{item['Product Code']}-{item['Supplier Batch No']}-{timestamp}"
        print(f"Generated tracking ID: {tracking_id}")
        
        # Update database
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        print("Connected to database")
        
        cursor.execute('''
            UPDATE received_products 
            SET barcode_data = ?, barcode_image = ?
            WHERE product_code = ? AND supplier_batch = ? AND status = 'Active'
        ''', (tracking_id, barcode_base64, item['Product Code'], item['Supplier Batch No']))
        print("Updated database")
        
        conn.commit()
        conn.close()
        print("Committed and closed database connection")
        
        # Update the item dictionary
        item['barcode_data'] = tracking_id
        item['barcode_image'] = barcode_base64
        print("Updated item dictionary")
        
        return True
        
    except Exception as e:
        print(f"Error saving barcode: {str(e)}")
        sg.popup_error(f'Error saving barcode: {str(e)}', font=FONT_NORMAL)
        return False

def save_as_pdf(report, filename):
    print(f"Saving report to {filename}...")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=10)
    
    # Split content into lines and write to PDF
    lines = report.split('\n')
    print(f"Lines: {lines}")
    for line in lines:
        # Remove any special characters used for formatting in the preview
        clean_line = line.replace('║', '|').replace('╔', '+').replace('╚', '+').replace('─', '-')
        print(f"Writing line to PDF: {clean_line}")
        pdf.cell(0, 5, txt=clean_line, ln=True)
    
    pdf.output(filename)
    print("Saved report to PDF.")

def save_as_csv(report, filename):
    print(f"Saving report to {filename}...")
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        print("Writing header row")
        writer.writerow(['Date', 'Product', 'Current Dept', 'Quantity', 'Status', 'Batch', 'Description', 'Processed By', 'Processing Date'])
        print("Writing data rows")
        writer.writerows(report)
        print("File closed, report saved.")

def initialize_database():
    print("Initializing database...")
    conn = sqlite3.connect('spatrac.db')
    print("Connected to database")
    cursor = conn.cursor()
    
    print("Creating table if it doesn't exist")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS received_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT,
            description TEXT,
            quantity REAL,
            unit TEXT,
            department TEXT,
            received_by TEXT,
            received_date TEXT,
            supplier_batch TEXT,
            sell_by_date TEXT,
            status TEXT DEFAULT 'Active',
            handling_history TEXT DEFAULT '',
            temperature_log TEXT DEFAULT '',
            processed_by TEXT,
            processing_date TEXT,
            barcode_data TEXT,
            barcode_image TEXT
        )
    ''')
    
    # Check if columns exist and add them if they don't
    print("Checking if columns exist")
    cursor.execute("PRAGMA table_info(received_products)")
    columns = [info[1] for info in cursor.fetchall()]
    
    required_columns = {
        'status': 'TEXT DEFAULT "Active"',
        'handling_history': 'TEXT DEFAULT ""',
        'temperature_log': 'TEXT DEFAULT ""',
        'processed_by': 'TEXT',
        'processing_date': 'TEXT',
        'barcode_data': 'TEXT',
        'barcode_image': 'TEXT'
    }
    
    print("Adding columns that don't exist")
    for col_name, col_type in required_columns.items():
        if col_name not in columns:
            print(f"Adding column {col_name} to database")
            cursor.execute(f'ALTER TABLE received_products ADD COLUMN {col_name} {col_type}')
    
    print("Committing changes")
    conn.commit()
    print("Closing database connection")
    conn.close()

def add_received_product(product, auth_system, window=None):
    """Add a new product to the received products database."""
    try:
        user_info = auth_system.get_current_user_info()
        if not user_info:
            print("No user logged in. Aborting product addition.")
            return False
            
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print("Initializing lists for tracking")
        # Initialize lists for tracking
        if 'Temperature Log' not in product or isinstance(product['Temperature Log'], str):
            product['Temperature Log'] = []
        if 'Handling History' not in product or isinstance(product['Handling History'], str):
            product['Handling History'] = []
            
        print("Adding receiving history")
        # Add receiving history
        product['Handling History'].append(
            f"Received on {current_time} by {user_info['username']} ({user_info['role']} - {user_info['department']})"
        )
        
        print("Adding receiving information")
        # Add receiving information
        product['Received Date'] = current_time
        product['Received By'] = user_info['username']
        product['Status'] = 'Active'
        product['Department'] = user_info['department']  # Add department information
        
        print("Connecting to database")
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        print("Inserting product into database...")
        cursor.execute('''
            INSERT INTO received_products (
                product_code, description, quantity, unit,
                supplier_batch, sell_by_date, status,
                received_date, received_by, handling_history,
                temperature_log, department, barcode_image, processed_by, processing_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product['Product Code'],
            product['Product Description'],
            product['Quantity'],
            product['Unit'],
            product['Supplier Batch No'],
            product['Sell By Date'],
            product['Status'],
            product['Received Date'],
            product['Received By'],
            json.dumps(product['Handling History']),
            json.dumps(product['Temperature Log']),
            product['Department'],
            product.get('barcode_image', ''),
            product.get('Processed By', ''),
            product.get('Processing Date', '')
        ))
        
        print("Committing changes")
        conn.commit()
        print("Closing database connection")
        conn.close()
        
        # If window is provided, refresh the display
        if window is not None:
            print("Refreshing display")
            refresh_display(window, [], auth_system)
            
        print("Product added successfully")
        return True
        
    except Exception as e:
        print(f"Error adding product: {str(e)}")
        sg.popup_error('Error', f'Failed to add product: {str(e)}', font=FONT_NORMAL)
        return False

def get_department_inventory(department):
    """
    Get the inventory for a specific department.
    
    Args:
        department: The department to get inventory for
        
    Returns:
        List of inventory items for the department
    """
    print(f"get_department_inventory called with department: {department}")
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT product_code, description, quantity, unit, supplier_batch, 
                   sell_by_date, received_date, received_by, status, department,
                   COALESCE(handling_history, '[]') as handling_history,
                   COALESCE(temperature_log, '[]') as temperature_log,
                   COALESCE(barcode_data, '') as barcode_data,
                   COALESCE(barcode_image, '') as barcode_image,
                   COALESCE(processed_by, '') as processed_by,
                   COALESCE(processing_date, '') as processing_date
            FROM received_products
            WHERE department = ? AND status = 'Active'
            ORDER BY received_date DESC
        ''', (department,))
        
        print("Query executed, fetching results...")
        # Get column names from cursor description
        columns = [desc[0] for desc in cursor.description]
        
        # Convert tuples to dictionaries
        inventory = []
        for row in cursor.fetchall():
            item = dict(zip(columns, row))
            # Convert to expected keys
            item['Product Code'] = item.pop('product_code')
            item['Product Description'] = item.pop('description')
            item['Quantity'] = item.pop('quantity')
            item['Unit'] = item.pop('unit')
            item['Supplier Batch No'] = item.pop('supplier_batch')
            item['Sell By Date'] = item.pop('sell_by_date')
            item['Delivery Date'] = item.pop('received_date')  # Align with display name
            item['Received By'] = item.pop('received_by')
            item['Status'] = item.pop('status')
            item['Department'] = item.pop('department')
            
            print(f"Processing item: {item}")
            
            # Parse JSON strings for lists
            try:
                item['Handling History'] = json.loads(item.pop('handling_history'))
            except json.JSONDecodeError:
                item['Handling History'] = []
                
            try:
                item['Temperature Log'] = json.loads(item.pop('temperature_log'))
            except json.JSONDecodeError:
                item['Temperature Log'] = []
            
            print(f"Updated item: {item}")
            
            # Add barcode data if available
            barcode_data = item.pop('barcode_data', '')
            barcode_image = item.pop('barcode_image', '')
            if barcode_data:
                item['barcode_data'] = barcode_data
            if barcode_image:
                item['barcode_image'] = barcode_image
            
            # Add processed_by and processing_date if available
            processed_by = item.pop('processed_by', '')
            processing_date = item.pop('processing_date', '')
            if processed_by:
                item['Processed By'] = processed_by
            if processing_date:
                item['Processing Date'] = processing_date
            
            print(f"Final item: {item}")
            
            inventory.append(item)
        
        return inventory
        
    except Exception as e:
        print(f"Error retrieving department inventory: {e}")
        return []
        
    finally:
        conn.close()

def update_inventory_table(window, inventory):
    """Update the inventory table with active (unprocessed) items."""
    # Filter for active items only
    active_items = [item for item in inventory if item.get('Status') == 'Active']
    
    print(f"Updating inventory table with {len(active_items)} active items.")
    
    # Update table with active items
    try:
        window['-RECEIVING_TABLE-'].update(values=[
            [item['Product Code'],
             item['Product Description'],
             item['Quantity'],
             item['Unit'],
             item.get('Supplier Batch No', ''),
             item.get('Sell By Date', ''),
             item.get('Delivery Date', ''),
             item.get('Received By', '')] for item in active_items
        ])
        print("Inventory table updated.")
    except (KeyError, AttributeError) as e:
        print(f"Error updating inventory table: {e}")
        pass

def create_database_management_tab():
    today = datetime.now()
    print("Initializing Database Management tab layout...")
    
    layout = [
        [sg.Text('Database Management', font=FONT_HEADER, justification='center', expand_x=True)],
        [sg.Frame('Search Records', [
            [sg.Text('Date Range:')],
            [sg.Text('From:'), 
             sg.Input(key='-DB-START-DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d'), enable_events=True),
             sg.CalendarButton('Choose', target='-DB-START-DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['primary']), key='-DB-START-CAL-'),
             sg.Text('To:'), 
             sg.Input(key='-DB-END-DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d'), enable_events=True),
             sg.CalendarButton('Choose', target='-DB-END-DATE-', format='%Y-%m-%d',
                             button_color=(COLORS['text'], COLORS['primary']), key='-DB-END-CAL-')],
            [sg.Text('Department:'), 
             sg.Combo(['All', 'Butchery', 'Bakery', 'HMR'], default_value='All', key='-DB-DEPT-', size=(20,1))],
            [sg.Text('Status:'),
             sg.Combo(['All', 'Active', 'Processed'], default_value='All', key='-DB-STATUS-', size=(20,1))],
            [sg.Text('Product Code:'), sg.Input(key='-DB-PRODUCT-CODE-', size=(20,1))],
            [sg.Button('Search', key='-DB-SEARCH-', button_color=(COLORS['text'], COLORS['primary']))]
        ])],
        [sg.Frame('Results', [
            [sg.Table(
                values=[], 
                headings=['Date', 'Product', 'Current Dept', 'Quantity', 'Status', 'Batch', 'Description', 'Processed By', 'Processing Date'],
                auto_size_columns=True,
                justification='left',
                num_rows=10,
                key='-DB-TABLE-',
                enable_events=True)
            ]
        ])],
        [sg.Frame('Actions', [
            [sg.Button('Export to CSV', key='-DB-EXPORT-CSV-', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Export to PDF', key='-DB-EXPORT-PDF-', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('View Details', key='-DB-VIEW-DETAILS-', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Delete All Active Products', key='-DB-DELETE-ALL-', button_color=(COLORS['text'], COLORS['danger']))]])],
    ]
    
    print("Database Management tab layout created successfully.")
    return sg.Tab('Database Management', layout, key='-DATABASE-TAB-')

def handle_database_management_events(event, values, window, inventory, auth_system):
    if not auth_system.is_manager():
        sg.popup_error('Access Denied', 'Only managers can access database management features.')
        return

    print(f"Handling event: {event}")

    if event == '-DB-SEARCH-':
        print("Event is '-DB-SEARCH-', searching database...")
        try:
            # Query database based on search criteria
            conn = sqlite3.connect('spatrac.db')
            cursor = conn.cursor()
            
            query = '''
                SELECT 
                    received_date, 
                    product_code, 
                    department, 
                    quantity, 
                    status, 
                    supplier_batch, 
                    description,
                    processed_by,
                    processing_date,
                    handling_history,
                    barcode_data,
                    barcode_image
                FROM received_products
                WHERE 1=1
            '''
            params = []
            
            if values['-DB-START-DATE-']:
                query += ' AND received_date >= ?'
                params.append(values['-DB-START-DATE-'])
            if values['-DB-END-DATE-']:
                query += ' AND received_date <= ?'
                params.append(values['-DB-END-DATE-'])
            if values['-DB-DEPT-'] != 'All':
                query += ' AND department = ?'
                params.append(values['-DB-DEPT-'])
            if values['-DB-STATUS-'] != 'All':
                # Convert status to match database value (Processed or active)
                status = 'Processed' if values['-DB-STATUS-'] == 'Processed' else 'active'
                query += ' AND status = ?'
                params.append(status)
            if values['-DB-PRODUCT-CODE-']:
                query += ' AND product_code LIKE ?'
                params.append(f"%{values['-DB-PRODUCT-CODE-']}%")
                
            print(f"Executing query: {query}")
            print(f"Params: {params}")
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Format results for display
            formatted_results = []
            for row in results:
                formatted_row = list(row[:9])  # Get all columns except handling_history, barcode_data, barcode_image
                formatted_results.append(formatted_row)
                
            window['-DB-TABLE-'].update(formatted_results)
            conn.close()
        except Exception as e:
            sg.popup_error('Database Error', f'Error searching database: {str(e)}')

    elif event == '-DB-EXPORT-CSV-':
        print("Event is '-DB-EXPORT-CSV-', exporting results to CSV...")
        if not window['-DB-TABLE-'].get():
            sg.popup_error('No Data', 'Please perform a search first.')
            return
        filename = sg.popup_get_file('Save CSV As', save_as=True, 
                                       file_types=(("CSV Files", "*.csv"),),
                                       default_extension='.csv')
        if filename:
            try:
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Date', 'Product', 'Current Dept', 'Quantity', 'Status', 'Batch', 'Description', 'Processed By', 'Processing Date'])
                    writer.writerows(window['-DB-TABLE-'].get())
                sg.popup('Success', f"Report saved as {filename}")
            except Exception as e:
                sg.popup_error('Export Error', f'Error saving CSV: {str(e)}')

    elif event == '-DB-EXPORT-PDF-':
        print("Event is '-DB-EXPORT-PDF-', exporting results to PDF...")
        if not window['-DB-TABLE-'].get():
            sg.popup_error('No Data', 'Please perform a search first.')
            return
        filename = sg.popup_get_file('Save PDF As', save_as=True, 
                                       file_types=(("PDF Files", "*.pdf"),),
                                       default_extension='.pdf')
        if filename:
            try:
                pdf = FPDF()
                pdf.add_page()
                
                # Set font
                pdf.set_font("Arial", "B", 16)
                
                # Title
                pdf.cell(0, 10, "SPATRAC Database Search Results", ln=True, align='C')
                pdf.ln(10)
                
                # Date Range
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, f"Date Range: {values['-DB-START-DATE-']} to {values['-DB-END-DATE-']}", ln=True)
                pdf.ln(5)
                
                # Results
                pdf.set_font("Arial", "", 10)
                for row in window['-DB-TABLE-'].get():
                    pdf.cell(0, 8, f"Date: {row[0]}", ln=True)
                    pdf.cell(0, 8, f"Product: {row[1]}", ln=True)
                    pdf.cell(0, 8, f"Department: {row[2]}", ln=True)
                    pdf.cell(0, 8, f"Quantity: {row[3]}", ln=True)
                    pdf.cell(0, 8, f"Status: {row[4]}", ln=True)
                    pdf.cell(0, 8, f"Batch: {row[5]}", ln=True)
                    pdf.cell(0, 8, f"Description: {row[6]}", ln=True)
                    pdf.cell(0, 8, f"Processed By: {row[7]}", ln=True)
                    pdf.cell(0, 8, f"Processing Date: {row[8]}", ln=True)
                    pdf.ln(5)
                
                # Save the PDF
                pdf.output(filename)
                sg.popup('Report saved successfully!', title='Success')
                
            except Exception as e:
                sg.popup_error('Export Error', f'Error saving PDF: {str(e)}')

    elif event == '-DB-VIEW-DETAILS-':
        print("Event is '-DB-VIEW-DETAILS-', viewing product details...")
        try:
            selected_rows = window['-DB-TABLE-'].SelectedRows
            if not selected_rows:
                sg.popup_error('No Selection', 'Please select a record to view details.')
                return
            
            table_data = window['-DB-TABLE-'].Values
            if not table_data:
                sg.popup_error('No Data', 'No data available to view.')
                return
                
            selected_row = table_data[selected_rows[0]]
            if not selected_row:
                sg.popup_error('Invalid Selection', 'Could not retrieve selected record.')
                return
                
            # Get full product details including handling history
            conn = sqlite3.connect('spatrac.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT *
                FROM received_products
                WHERE product_code = ? AND supplier_batch = ?
            ''', (selected_row[1], selected_row[5]))
            
            result = cursor.fetchone()
            if result:
                column_names = [desc[0] for desc in cursor.description]
                product_details = dict(zip(column_names, result))
                
                # Convert handling history string back to list if it exists
                if product_details.get('handling_history'):
                    product_details['handling_history'] = product_details['handling_history'].split('\n')
                
                show_database_product_details(product_details, auth_system)
            else:
                sg.popup_error('Record Not Found', 'Could not find the selected record in the database.')
            
            conn.close()
        except Exception as e:
            sg.popup_error('Error', f'An error occurred while viewing details: {str(e)}')

def load_final_products(department):
    """Load final products for a specific department."""
    try:
        print(f"Loading final products for department: {department}")
        with open(f'data/{department.lower()}_final_products.csv', 'r') as file:
            reader = csv.DictReader(file)
            print(f"Successfully loaded final products for department: {department}")
            return list(reader)
    except FileNotFoundError:
        print(f"File not found for final products of department: {department}")
        return []

def create_reports_tab():
    today = datetime.now()
    print("Initializing Reports tab layout...")
    layout = [
        [sg.Text('Reports', font=FONT_HEADER, justification='center', expand_x=True)],
        [sg.Frame('Report Options', [
            [sg.Text('Report Type:'),
             sg.Combo(['Inventory Summary', 'Traceability Report'], 
                     default_value='Inventory Summary', key='-REPORT_TYPE-', size=(20,1))],
            [sg.Text('Date Range:')],
            [sg.Text('From:'), 
             sg.Input(key='-START_DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d')),
             sg.CalendarButton('Choose', target='-START_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['primary']))],
            [sg.Text('To:'), 
             sg.Input(key='-END_DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d')),
             sg.CalendarButton('Choose', target='-END_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['primary']))],
            [sg.Button('Generate Report', key='-GENERATE_REPORT-', button_color=(COLORS['text'], COLORS['primary']))]
        ])],
        [sg.Frame('Report Preview', [
            [sg.Multiline(size=(80, 20), key='-REPORT_PREVIEW-', disabled=True)]
        ])],
        [sg.Frame('Export Options', [
            [sg.Button('Save as PDF', key='-SAVE_PDF-', button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Button('Save as CSV', key='-SAVE_CSV-', button_color=(COLORS['text'], COLORS['secondary']))]
        ])]
    ]
    print("Reports tab layout created successfully.")
    print("Layout:", layout)
    return layout

def save_report_as_pdf(filename, report_data, report_type, start_date, end_date, auth_system):
    """Save the report as a PDF file."""
    try:
        print("Initializing PDF creation...")
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        print("Adding header to PDF...")
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"SPATRAC - {report_type}", ln=True, align='C')
        pdf.ln(5)
        
        # User Info
        print("Fetching user information...")
        user_info = auth_system.get_current_user_info()
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"Department: {user_info['department']}", ln=True)
        pdf.cell(0, 8, f"Generated by: {user_info['username']} ({user_info['role']} - {user_info['department']}) - {user_info['department']}", ln=True)
        pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.cell(0, 8, f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", ln=True)
        pdf.ln(10)
        
        if report_type == 'Inventory Summary':
            print("Generating Inventory Summary section...")
            # Summary Statistics
            total_items = len(report_data)
            unique_products = len(set(item.get('Product Code', '') for item in report_data))
            total_quantity = sum(float(item.get('Quantity', 0)) for item in report_data)
            
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Summary Statistics", ln=True)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 8, f"Total Unique Products: {unique_products}", ln=True)
            pdf.cell(0, 8, f"Total Items: {total_items}", ln=True)
            pdf.cell(0, 8, f"Total Quantity: {total_quantity}", ln=True)
            pdf.ln(10)
            
            # Detailed Inventory
            print("Adding Detailed Inventory...")
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Detailed Inventory", ln=True)
            pdf.set_font("Arial", "", 12)
            
            # Group items by product code
            product_groups = {}
            for item in report_data:
                code = item.get('Product Code', 'N/A')
                if code not in product_groups:
                    product_groups[code] = {
                        'description': item.get('Description', 'N/A'),
                        'quantity': 0,
                        'unit': item.get('Unit', 'N/A')
                    }
                product_groups[code]['quantity'] += float(item.get('Quantity', 0))
            
            for code, data in product_groups.items():
                pdf.cell(0, 8, f"Product Code: {code}", ln=True)
                pdf.cell(0, 8, f"Description: {data['description']}", ln=True)
                pdf.cell(0, 8, f"Total Quantity: {data['quantity']} {data['unit']}", ln=True)
                pdf.ln(5)
                
        elif report_type == 'Traceability Report':
            print("Generating Traceability Report section...")
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Traceability Details", ln=True)
            
            for item in report_data:
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, "Product Information", ln=True)
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 8, f"• Code: {item.get('Product Code', 'N/A')}", ln=True)
                pdf.cell(0, 8, f"• Description: {item.get('Description', 'N/A')}", ln=True)
                pdf.cell(0, 8, f"• Batch: {item.get('Supplier Batch', 'N/A')}", ln=True)
                pdf.cell(0, 8, f"• Sell By: {item.get('Sell By Date', 'N/A')}", ln=True)
                
                pdf.ln(5)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, "Tracking Information", ln=True)
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 8, f"• Received: {item.get('Received Date', 'N/A')}", ln=True)
                pdf.cell(0, 8, f"• Received By: {item.get('Received By', 'N/A')}", ln=True)
                pdf.cell(0, 8, f"• Status: {item.get('Status', 'N/A')}", ln=True)
                pdf.ln(10)
        
        # Footer
        print("Adding footer to PDF...")
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 10, "Report End", ln=True, align='C')
        pdf.cell(0, 10, "Generated by SPATRAC System", ln=True, align='C')
        pdf.cell(0, 10, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ln=True, align='C')
        
        print("Saving PDF to file...")
        pdf.output(filename)
        print("PDF saved successfully.")
        return True
    except Exception as e:
        print(f"Error creating PDF: {str(e)}")
        raise Exception(f"Error creating PDF: {str(e)}")

def save_report_as_csv(filename, report_data, report_type, start_date, end_date, auth_system):
    try:
        print(f"Starting CSV report generation: {filename}")
        user_info = auth_system.get_current_user_info()
        print(f"User info retrieved: {user_info}")
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            print("CSV file opened and writer initialized.")
            
            # Write header rows
            writer.writerow(['SPATRAC - ' + report_type])
            writer.writerow(['Department: ' + user_info['department']])
            writer.writerow(['Generated by: ' + user_info['username'] + ' (' + user_info['role'] + ')'])
            writer.writerow(['Date: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['Period: ' + start_date.strftime('%Y-%m-%d') + ' to ' + end_date.strftime('%Y-%m-%d')])
            writer.writerow([])  # Empty row for spacing
            print("Header rows written to CSV.")
            
            if report_type == 'Inventory Summary':
                print("Generating Inventory Summary section.")
                # Calculate summary statistics
                total_items = len(report_data)
                unique_products = len(set(item.get('Product Code', '') for item in report_data))
                total_quantity = sum(float(item.get('Quantity', 0)) for item in report_data)
                
                # Write summary statistics
                writer.writerow(['Summary Statistics'])
                writer.writerow(['Total Unique Products', unique_products])
                writer.writerow(['Total Items', total_items])
                writer.writerow(['Total Quantity', total_quantity])
                writer.writerow([])  # Empty row for spacing
                print("Summary statistics written to CSV.")
                
                # Write detailed inventory
                writer.writerow(['Detailed Inventory'])
                writer.writerow(['Product Code', 'Description', 'Quantity', 'Unit'])
                
                # Group items by product code
                product_groups = {}
                for item in report_data:
                    code = item.get('Product Code', 'N/A')
                    if code not in product_groups:
                        product_groups[code] = {
                            'description': item.get('Description', 'N/A'),
                            'quantity': 0,
                            'unit': item.get('Unit', 'N/A')
                        }
                    product_groups[code]['quantity'] += float(item.get('Quantity', 0))
                
                for code, data in product_groups.items():
                    writer.writerow([
                        code,
                        data['description'],
                        data['quantity'],
                        data['unit']
                    ])
                print("Detailed inventory written to CSV.")
                    
            elif report_type == 'Traceability Report':
                print("Generating Traceability Report section.")
                writer.writerow(['Traceability Details'])
                writer.writerow(['Product Code', 'Description', 'Batch', 'Sell By', 'Received Date', 'Received By', 'Status'])
                
                for item in report_data:
                    writer.writerow([
                        item.get('Product Code', 'N/A'),
                        item.get('Description', 'N/A'),
                        item.get('Supplier Batch', 'N/A'),
                        item.get('Sell By Date', 'N/A'),
                        item.get('Received Date', 'N/A'),
                        item.get('Received By', 'N/A'),
                        item.get('Status', 'N/A')
                    ])
                print("Traceability details written to CSV.")
            
            # Write footer
            writer.writerow([])  # Empty row for spacing
            writer.writerow(['Report End'])
            writer.writerow(['Generated by SPATRAC System'])
            writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            print("Footer written to CSV.")
            
        print("CSV report generation completed successfully.")
        return True
    except Exception as e:
        print(f"Error saving CSV: {str(e)}")
        raise Exception(f"Error saving CSV: {str(e)}")

def format_report_for_display(report_data, report_type, auth_system):
    """Format the report data for display in the GUI."""
    print(f"Formatting report for display: {report_type}")
    
    user_info = auth_system.get_current_user_info()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"User info: {user_info}, Current time: {current_time}")
    
    header = f"""
SPATRAC {report_type}
─────────────────────────────────────────────────────────────────
Generated by: {user_info['username']}
Department: {user_info['department']}
Date: {current_time}
─────────────────────────────────────────────────────────────────

"""
    print("Header formatted.")
    
    body = ""
    if report_type == 'Inventory Summary':
        for item in report_data:
            body += f"""
Product Code: {item.get('Product Code', 'N/A')}
Name: {item.get('Name', 'N/A')}
Quantity: {item.get('Quantity', 'N/A')}
Status: {item.get('Status', 'N/A')}
─────────────────────────────────────────────────────────────────"""
            print(f"Added inventory summary for Product Code: {item.get('Product Code', 'N/A')}")
    
    elif report_type == 'Traceability Report':
        for item in report_data:
            body += f"""
Product Code: {item.get('Product Code', 'N/A')}
Description: {item.get('Description', 'N/A')}
Supplier Batch: {item.get('Supplier Batch', 'N/A')}
Sell By Date: {item.get('Sell By Date', 'N/A')}
Received Date: {item.get('Received Date', 'N/A')}
Received By: {item.get('Received By', 'N/A')}
Status: {item.get('Status', 'N/A')}
─────────────────────────────────────────────────────────────────"""
            print(f"Added traceability report for Product Code: {item.get('Product Code', 'N/A')}")
    
    footer = f"""

Report End
Generated by SPATRAC System
{current_time}
"""
    print("Footer formatted.")
    
    return header + body + footer

def show_product_details(product, auth_system):
    """Display detailed product information including barcode."""
    print("Entering show_product_details")
    if not product:
        print("No product selected")
        sg.popup_error('No product selected', font=FONT_NORMAL)
        return
        
    # Convert barcode image from base64 if available
    barcode_image_path = None
    print(f"Checking for barcode image in product: {product.get('barcode_image', 'N/A')}")
    if product.get('barcode_image'):
        print("Barcode image found, attempting to decode and save")
        try:
            barcode_data = base64.b64decode(product['barcode_image'])
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_file.write(barcode_data)
                barcode_image_path = temp_file.name
                print(f"Barcode image saved to: {barcode_image_path}")
        except Exception as e:
            print(f"Error loading barcode image: {e}")
            
    # Create the layout
    layout = [
        [sg.Text('Product Details', font=('Helvetica', 12, 'bold'))],
        [sg.Text(f"Product Code: {product['Product Code']}", font=FONT_NORMAL)],
        [sg.Text(f"Description: {product['Product Description']}", font=FONT_NORMAL)],
        [sg.Text(f"Supplier Batch: {product.get('Supplier Batch No', 'N/A')}", font=FONT_NORMAL)],
        [sg.Text(f"Sell by Date: {product.get('Sell By Date', 'N/A')}", font=FONT_NORMAL)],
        [sg.Text(f"Status: {product.get('Status', 'N/A')}", font=FONT_NORMAL)],
    ]
    
    # Add barcode section if available
    print(f"Checking for barcode data in product: {product.get('barcode_data', 'N/A')}")
    if product.get('barcode_data'):
        print("Barcode data found, adding to layout")
        layout.extend([
            [sg.Text('Barcode Information', font=('Helvetica', 10, 'bold'))],
            [sg.Text(f"Barcode Data: {product['barcode_data']}", font=FONT_NORMAL)],
        ])
        if barcode_image_path:
            layout.append([sg.Image(barcode_image_path, size=(300, 100))])
    
    if product.get('processed_by'):
        print("Adding processing information to layout...")
        layout.extend([
            [sg.Text('Processing Information', font=('Helvetica', 10, 'bold'))],
            [sg.Text(f"Processed By: {product['processed_by']}")],
            [sg.Text(f"Processing Date: {product.get('processing_date', 'N/A')}")],
        ])
    
    layout.extend([
        [sg.Text('Handling History:', font=('Helvetica', 10, 'bold'))],
        [sg.Multiline(product.get('Handling History', 'No handling history available'), 
                     size=(60, 5), disabled=True, font=FONT_NORMAL)],
        [sg.Text('Temperature Log:', font=('Helvetica', 10, 'bold'))],
        [sg.Multiline(format_temperature_log(product.get('Temperature Log', [])), 
                     size=(60, 3), disabled=True, font=FONT_NORMAL)],
        [sg.Button('Close', font=FONT_NORMAL)]
    ])
    
    details_window = sg.Window('Product Details', layout, modal=True, finalize=True)
    
    # Center the window on screen
    details_window.move(details_window.current_location()[0], 0)
    
    while True:
        event, _ = details_window.read()
        print(f"Event: {event}")
        if event in (sg.WIN_CLOSED, 'Close'):
            if barcode_image_path and os.path.exists(barcode_image_path):
                try:
                    os.unlink(barcode_image_path)
                    print(f"Removed temporary barcode file: {barcode_image_path}")
                except Exception as e:
                    print(f"Error removing temporary barcode file: {e}")
            break
            
    details_window.close()
    print("Exiting show_product_details")

def format_temperature_log(temp_log):
    """Format temperature log entries for display."""
    print("Starting to format temperature log.")

    if not temp_log or not isinstance(temp_log, list):
        print("Temperature log is empty or not a list.")
        return 'No temperature readings available'
        
    formatted_entries = []
    for entry in temp_log:
        if isinstance(entry, dict):
            print(f"Formatting entry: {entry}")
            formatted_entries.append(
                f"{entry.get('timestamp', 'N/A')} - {entry.get('temperature', 'N/A')}°C at {entry.get('location', 'N/A')}"
            )
        else:
            print(f"Entry is not a dictionary: {entry}")
            formatted_entries.append(str(entry))
            
    result = '\n'.join(formatted_entries) if formatted_entries else 'No temperature readings available'
    print(f"Formatted temperature log: {result}")
    return result

def generate_inventory_summary(inventory, start_date, end_date, auth_system):
    """Generate an inventory summary report for the specified date range."""
    try:
        if not auth_system or not auth_system.get_current_user_info():
            raise ValueError("User not authenticated")
            
        print("Starting to generate inventory summary")
        print(f"Inventory has {len(inventory)} items")
        print(f"Filtering inventory by date range: {start_date.date()} to {end_date.date()}")
        
        # Filter inventory by date range
        filtered_inventory = [
            item for item in inventory 
            if start_date.date() <= datetime.strptime(item.get('Received Date', '1900-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S').date() <= end_date.date()
        ]
        
        print(f"Filtered inventory has {len(filtered_inventory)} items")
        return filtered_inventory
    except Exception as e:
        raise Exception(f"Error generating inventory summary: {str(e)}")
        

def generate_traceability_report(inventory, start_date, end_date, auth_system):
    """Generate a traceability report for the specified date range."""
    try:
        if not auth_system or not auth_system.get_current_user_info():
            raise ValueError("User not authenticated")
            
        print("Starting to generate traceability report")
        print(f"Inventory has {len(inventory)} items")
        print(f"Filtering inventory by date range: {start_date.date()} to {end_date.date()}")
        
        # Filter inventory by date range
        filtered_inventory = [
            item for item in inventory 
            if start_date.date() <= datetime.strptime(item.get('Received Date', '1900-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S').date() <= end_date.date()
        ]
        
        print(f"Filtered inventory has {len(filtered_inventory)} items")
        print("Sorting by received date for better traceability")
        
        # Sort by received date for better traceability
        filtered_inventory.sort(key=lambda x: datetime.strptime(x.get('Received Date', ''), '%Y-%m-%d %H:%M:%S'), reverse=True)
        
        print("Enhancing items with handling history")
        # Enhance each item with handling history if available
        for item in filtered_inventory:
            if isinstance(item.get('Handling History', ''), list):
                print(f"Formatting handling history for item: {item}")
                item['Handling History'] = '\n'.join(item['Handling History'])
            if isinstance(item.get('Temperature Log', ''), list):
                # Format temperature log
                item['Temperature Log'] = format_temperature_log(item['Temperature Log'])
        
        print("Returning filtered and enhanced inventory")
        return filtered_inventory
    except Exception as e:
        raise Exception(f"Error generating traceability report: {str(e)}")

def delete_all_active_products():
    """Delete all active products from the database."""
    try:
        print("Starting to delete all active products from database")
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        print("Getting count of active products before deletion")
        cursor.execute('SELECT COUNT(*) FROM received_products WHERE status = ?', ('Active',))
        count = cursor.fetchone()[0]
        print(f"Found {count} active products")
        
        if count == 0:
            print("No active products found to delete")
            return False, "No active products found to delete"
        
        print("Deleting all products with 'Active' status")
        cursor.execute('DELETE FROM received_products WHERE status = ?', ('Active',))
        print("Deleted all active products")
        
        print("Committing and closing database connection")
        conn.commit()
        conn.close()
        print("Database connection closed")
        
        return True, f"Successfully deleted {count} active products"
    except Exception as e:
        print(f"Error deleting active products: {e}")
        return False, f"Error deleting active products: {str(e)}"

if __name__ == "__main__":
    update_database_schema()  # Initialize/update database schema
    migrate_existing_data()
    file_paths = ['Butchery reports Big G.csv', 'Bakery Big G.csv', 'HMR Big G.csv']
    df = load_data(file_paths)
    create_gui(df)