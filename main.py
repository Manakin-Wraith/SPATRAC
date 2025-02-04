import pandas as pd
import PySimpleGUI as sg
import csv
from fpdf import FPDF
from datetime import datetime
import sqlite3
import json
import io
from barcode import Code128
from barcode.writer import ImageWriter
from auth_system import AuthSystem
import logging
import base64
import os
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
            df = pd.read_csv(file_path, encoding='iso-8859-1', sep=';')
            df.columns = df.iloc[0]
            df = df.iloc[1:]  # Remove the first row since it's now the header
            
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
        except FileNotFoundError:
            print(f"Error: File {file_path} not found")
        except pd.errors.EmptyDataError:
            print(f"Error: File {file_path} is empty")
        except pd.errors.ParserError as e:
            print(f"Error parsing file {file_path}: {str(e)}")
    
    if not dfs:
        print("No valid data files found")
        return pd.DataFrame()
        
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
        product = df[df['Product Code'] == product_code].iloc[0].to_dict()
        
        # Create a new product entry
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
        
        # Record temperature before adding to inventory
        temp_log = record_temperature_popup()
        if temp_log is None:
            sg.popup_error('Temperature recording cancelled. Product not received.', font=FONT_NORMAL)
            return None
            
        new_product['Temperature Log'].append(temp_log)
        
        # Add the product to inventory
        if add_received_product(new_product, auth_system, window):
            return new_product
        return None
        
    except Exception as e:
        sg.popup_error('Error', f'Failed to deliver product: {str(e)}', font=FONT_NORMAL)
        return None

def approve_delivery(product, auth_system):
    current_user = auth_system.get_current_user_info()
    approval_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product['Status'] = 'Delivery Approved'
    product['Delivery Approved By'] = current_user["username"]
    product['Delivery Approval Date'] = approval_date
    product['Handling History'] += f"\nDelivery approved at {approval_date} by {current_user['username']}"
    return product

def process_product(product, auth_system):
    current_user = auth_system.get_current_user_info()
    processing_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Get temperature reading
    temp_reading = record_temperature_popup()
    if temp_reading is None:  # User cancelled temperature recording
        return None
        
    # Update product status and details
    product['Status'] = 'Processed'  # This will be used by update_product_in_database
    product['Processing Date'] = processing_date
    product['Processed By'] = current_user['username']
    product['Current Location'] = f"{product['Department']} Processing"
    
    # Create received info using Delivery Date
    received_info = (f"Originally received on {product.get('Delivery Date', 'Unknown Date')} "
                    f"by {product.get('Received By', 'Unknown')}")
    
    # Add detailed handling history with temperature
    if not product.get('Handling History'):
        product['Handling History'] = received_info
    product['Handling History'] += (f"\nProcessed at {processing_date} "
                                  f"by {current_user['username']} in {product['Department']}\n"
                                  f"Temperature reading: {temp_reading}\n"
                                  f"Product journey: {received_info} → Processed")
    
    # Update temperature log
    if not product.get('Temperature Log'):
        product['Temperature Log'] = []
    product['Temperature Log'].append(f"{processing_date}: {temp_reading}")
    
    # Update the product in the database
    update_product_in_database(product)
    
    return product

# Barcode generation
def generate_barcode(data):
    code128 = Code128(data, writer=ImageWriter())
    rv = io.BytesIO()
    code128.write(rv)
    image = Image.open(rv)
    image.thumbnail((300, 300))
    return image

def generate_product_barcode(product_code, batch_no, sell_by_date):
    """Generate a barcode for a product using Code128 format."""
    try:
        # Add timestamp to create a unique identifier
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        combined_batch = f"{product_code}-{batch_no}-{timestamp}"
        
        # Generate the barcode in memory
        code128 = Code128(combined_batch, writer=ImageWriter())
        
        # Save barcode to 'barcodes' directory
        barcode_filename = f'barcodes/{combined_batch}.png'
        code128.write(barcode_filename)
        
        # Convert to base64
        with open(barcode_filename, 'rb') as image_file:
            barcode_image = base64.b64encode(image_file.read()).decode()
        
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
            return False, "User not authenticated"

        # Generate barcode
        barcode_info = generate_product_barcode(
            values['-PRODUCT_CODE-'],
            values['-SUPPLIER_BATCH-'],
            values['-SELL_BY_DATE-']
        )
        
        if not barcode_info:
            return False, "Failed to generate barcode"

        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO received_products (
                product_code, description, quantity, unit, 
                supplier_batch, sell_by_date, received_date,
                received_by, status, department, handling_history,
                tracking_id, barcode_image, department_manager, supplier_name, supplier_address, country_of_origin, packaging_type, food_handler_name, packaging_batch_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            f"{values['-PRODUCT_CODE-']}-{values['-SUPPLIER_BATCH-']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            barcode_info['barcode_image'],
            current_user['username'],  # department_manager
            'Supplier Name',  # supplier_name
            'Supplier Address',  # supplier_address
            'Country of Origin',  # country_of_origin
            'Packaging Type',  # packaging_type
            current_user['username'],  # food_handler_name
            values['-SUPPLIER_BATCH-']  # packaging_batch_code
        ))
        
        conn.commit()
        conn.close()
        return True, "Product added successfully with barcode"
        
    except sqlite3.Error as e:
        return False, f"Database error: {str(e)}"
    except Exception as e:
        return False, f"Error adding product: {str(e)}"

def show_database_product_details(product, auth_system):
    """Display detailed product information from the database view."""
    user_info = auth_system.get_current_user_info()
    manager_info = f"Viewed by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Viewed by: N/A"
    
    # Create temporary file for barcode image if available
    barcode_image_path = None
    if product.get('barcode_image'):
        try:
            import tempfile
            from PIL import Image
            import io
            
            # Convert base64 to image
            image_data = base64.b64decode(product['barcode_image'])
            image = Image.open(io.BytesIO(image_data))
            
            # Create temporary file
            temp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            image.save(temp.name, format='PNG')
            temp.close()
            barcode_image_path = temp.name
        except Exception as e:
            print(f"Error creating barcode image: {str(e)}")
    
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
    
    # Add barcode section if available
    if product.get('barcode_data'):
        layout.extend([
            [sg.Text('Barcode Information', font=('Helvetica', 10, 'bold'))],
            [sg.Text(f"Barcode Data: {product['barcode_data']}")],
        ])
        if barcode_image_path:
            layout.append([sg.Image(barcode_image_path, size=(300, 100))])
    
    # Add processing information if available
    if product.get('processed_by'):
        layout.extend([
            [sg.Text('Processing Information', font=('Helvetica', 10, 'bold'))],
            [sg.Text(f"Processed By: {product['processed_by']}")],
            [sg.Text(f"Processing Date: {product.get('processing_date', 'N/A')}")],
        ])
    
    layout.extend([
        [sg.Text('Handling History:', font=('Helvetica', 10, 'bold'))],
        [sg.Multiline(product.get('handling_history', 'No handling history available'), size=(60, 5), disabled=True)],
        [sg.Text('Temperature Log:', font=('Helvetica', 10, 'bold'))],
        [sg.Multiline('\n'.join([str(entry) for entry in product.get('temperature_log', ['No temperature log available'])]), size=(60, 3), disabled=True)],
        [sg.Button('Close')]
    ])
    
    details_window = sg.Window('Database Product Details', layout, modal=True, finalize=True)
    
    # Center the window on screen
    details_window.move(details_window.current_location()[0], 0)
    
    while True:
        event, _ = details_window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
    
    details_window.close()
    
    # Clean up temporary barcode image file
    if barcode_image_path:
        try:
            import os
            os.unlink(barcode_image_path)
        except:
            pass

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
                 create_database_management_tab()]
            ], key='-TABGROUP-', expand_x=True, expand_y=True)],
            [sg.Button('Logout', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Button('Exit', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary']))]
        ]

        window = sg.Window('SPATRAC', layout, finalize=True, resizable=True, size=(1200, 800))
        
        inventory = []

        while True:
            event, values = window.read(timeout=100)
            if event in (sg.WIN_CLOSED, 'Exit'):
                return
            if event == 'Logout':
                auth_system.logout()
                window.close()
                break

            handle_product_management_events(event, values, window, df, inventory, auth_system)
            handle_receiving_events(event, values, window, inventory, auth_system)
            handle_recipes_events(event, values, window, df)
            handle_reports_events(event, values, window, inventory, auth_system)  # Added auth_system
            handle_database_management_events(event, values, window, inventory, auth_system)

        window.close()

def create_product_management_tab(df, departments):
    all_product_descriptions = sorted(df['Product Description'].unique().tolist())
    
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
    return layout  # Return just the layout instead of wrapping it in a Tab

def create_recipes_tab():
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
    return layout

def create_department_window(department, processed_products, final_products):
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
    return sg.Window(f"{department} Processing", layout, finalize=True)

def get_search_suggestions(df, search_term):
    suggestions = df[df['Product Description'].str.contains(search_term, case=False, na=False)]['Product Description'].tolist()
    return suggestions[:10]  # Limit to top 10 suggestions

def handle_product_management_events(event, values, window, df, inventory, auth_system):
    """Handle events in the Product Management tab."""
    if event == '-DELIVER-':
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
        search_term = values['-SEARCH-']
        if search_term:
            suggestions = get_search_suggestions(df, search_term)
            window['-SUGGESTIONS-'].update(values=suggestions, visible=True)
        else:
            window['-SUGGESTIONS-'].update(values=[], visible=False)

    if event == '-SUGGESTIONS-':
        if values['-SUGGESTIONS-']:
            selected_product = values['-SUGGESTIONS-'][0]
            window['-PRODUCT_DESC-'].update(value=selected_product)
            window['-SUGGESTIONS-'].update(visible=False)
            product_info = df[df['Product Description'] == selected_product].iloc[0]
            window['-DEPARTMENT-'].update(product_info['Department'])
            window['-PRODUCT-'].update(product_info['Product Code'])
            window['-SUPPLIER_PRODUCT-'].update(product_info['Supplier Product Code'])
    
    if event == '-PRODUCT_DESC-':
        selected_product = values['-PRODUCT_DESC-']
        if selected_product:
            product_info = df[df['Product Description'] == selected_product].iloc[0]
            window['-DEPARTMENT-'].update(product_info['Department'])
            window['-PRODUCT-'].update(product_info['Product Code'])
            window['-SUPPLIER_PRODUCT-'].update(product_info['Supplier Product Code'])

    if event == 'Search':
        search_term = values['-SEARCH-']
        if search_term:
            suggestions = get_search_suggestions(df, search_term)
            window['-PRODUCT_DESC-'].update(values=suggestions)
        else:
            all_product_descriptions = sorted(df['Product Description'].unique().tolist())
            window['-PRODUCT_DESC-'].update(values=all_product_descriptions)        

def update_department_tables(window, inventory):
    # Function kept for compatibility but no longer updates department tables
    pass

def handle_receiving_events(event, values, window, inventory, auth_system):
    if event == '-RECEIVING_TABLE-':
        return
    
    if event == 'View Details':
        selected_rows = values['-RECEIVING_TABLE-']
        if not selected_rows:
            sg.popup('Please select a product to view details', font=FONT_NORMAL)
            return
        
        # Get active items from inventory
        active_items = [item for item in inventory if item.get('Status') == 'Active']
        if not active_items or selected_rows[0] >= len(active_items):
            sg.popup('Selected product not found', font=FONT_NORMAL)
            return
            
        selected_product = active_items[selected_rows[0]]
        show_detailed_traceability(selected_product, auth_system)
    
    elif event == 'View Processed Details':
        selected_rows = values['-PROCESSED_TABLE-']
        if not selected_rows:
            sg.popup('Please select a processed product to view details', font=FONT_NORMAL)
            return
            
        # Get processed items from inventory
        processed_items = [item for item in inventory if item.get('Status') == 'Processed']
        if not processed_items or selected_rows[0] >= len(processed_items):
            sg.popup('Selected processed product not found', font=FONT_NORMAL)
            return
            
        selected_product = processed_items[selected_rows[0]]
        show_detailed_traceability(selected_product, auth_system)
    
    elif event == 'Process Selected':
        selected_rows = values['-RECEIVING_TABLE-']
        if not selected_rows:
            sg.popup('Please select products to process', font=FONT_NORMAL)
            return
            
        user_info = auth_system.get_current_user_info()
        if not user_info or user_info['role'] != 'Manager':
            sg.popup_error('You are not authorized to process products. Only Managers can process products.', font=FONT_NORMAL)
            return
            
        # Get active items from inventory
        active_items = [item for item in inventory if item.get('Status') == 'Active']
        if not active_items:
            sg.popup('No active products found', font=FONT_NORMAL)
            return
            
        selected_products = [active_items[row] for row in selected_rows if row < len(active_items)]
        if not selected_products:
            sg.popup('Selected products not found', font=FONT_NORMAL)
            return
            
        process_selected_products(auth_system, inventory, selected_products, window)
        # Update both tables after processing
        update_inventory_table(window, inventory)
        update_processed_table(window, inventory)
    
    elif event == 'Delete All':
        # Get current user's info to check login status and role
        current_user = auth_system.get_current_user_info()
        if current_user is None:
            sg.popup_error('Access Denied', 'Please log in to delete products.', font=FONT_NORMAL)
            return
            
        if current_user['role'] != 'Manager':
            sg.popup_error('Access Denied', 'Only Managers can delete all products.', font=FONT_NORMAL)
            return
        
        # Show a confirmation dialog before deleting
        if sg.popup_yes_no(
            'Confirm Delete All', 
            'This will delete ALL active products from the database.\n'
            'This action cannot be undone.\n\n'
            'Do you want to continue?',
            font=FONT_NORMAL
        ) == 'Yes':
            success, message = delete_all_active_products()
            if success:
                sg.popup('Success', message, font=FONT_NORMAL)
                # Refresh the display after deletion
                refresh_display(window, inventory, auth_system)
            else:
                sg.popup_error('Error', message, font=FONT_NORMAL)
    
    elif event == 'Refresh':
        # Get current user's info to check login status
        current_user = auth_system.get_current_user_info()
        if current_user is None:
            sg.popup_error('Access Denied', 'Please log in to refresh data.', font=FONT_NORMAL)
            return
        
        # Show a confirmation dialog before refreshing
        if sg.popup_yes_no(
            'Confirm Refresh', 
            'This will refresh unprocessed items from the database.\n'
            'Processed items will not be affected.\n\n'
            'Do you want to continue?',
            font=FONT_NORMAL
        ) == 'Yes':
            refresh_display(window, inventory, auth_system)

def department_login_window(auth_system, inventory, selected_rows, main_window):
    """Show department login window for processing products."""
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
    
    window = sg.Window('Department Manager Login', layout, finalize=True)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            window.close()
            return False
            
        if event == 'Login':
            username = values['-USERNAME-']
            password = values['-PASSWORD-']
            
            if auth_system.login(username, password):
                window.close()
                return True
            else:
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
        return
        
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Record temperature for each product
    for product in selected_products:
        temp_log = record_temperature_popup()
        if temp_log:
            # Initialize Temperature Log as a list if it doesn't exist or is a string
            if 'Temperature Log' not in product or isinstance(product['Temperature Log'], str):
                product['Temperature Log'] = []
            product['Temperature Log'].append(temp_log)
            
        # Update product status and processing info
        product['Status'] = 'Processed'
        product['Processing Date'] = current_time
        product['Processed By'] = user_info['username']
        
        # Handle Handling History - convert from string to list if needed
        if 'Handling History' not in product:
            product['Handling History'] = []
        elif isinstance(product['Handling History'], str):
            # If it's a string, convert it to a list with the existing history as the first item
            product['Handling History'] = [product['Handling History']]
            
        # Add new history entry
        product['Handling History'].append(
            f"Processed on {current_time} by {user_info['username']} ({user_info['role']} - {user_info['department']})"
        )
        
        # Update the database with the processed product information
        update_product_in_database(product)
    
    # Update the display
    update_inventory_table(window, inventory)
    update_processed_table(window, inventory)
    
    sg.popup('Success', f'{len(selected_products)} products processed successfully', font=FONT_NORMAL)

def update_product_in_database(product):
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    # Convert handling history to string for storage if it's a list
    handling_history = product['Handling History']
    if isinstance(handling_history, list):
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
    
    conn.commit()
    conn.close()

def handle_department_window(window, processed_products, final_products):
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
        elif event == 'Match Products':
            matched_products = match_products(processed_products, final_products)
            window['-MATCHED_TABLE-'].update(matched_products)
    window.close()

def match_products(processed_products, final_products):
    matched = []
    for processed in processed_products:
        processed_code = processed[0]  # Get the ingredient code
        # Find all recipes that use this ingredient
        for final_product in final_products:
            if processed_code == final_product[2]:  # Check if ingredient code matches
                # Create a row with all necessary information
                matched.append([
                    final_product[0],  # Final Product Code
                    final_product[1],  # Final Product Name
                    processed_code,    # Ingredient Code
                    processed[1],      # Ingredient Description
                    final_product[4]   # Required Quantity
                ])
    return matched


def handle_recipes_events(event, values, window, df):
    if event == '__TIMEOUT__':
        update_recipes_table(window)
        return

    if event == 'Add Ingredient':
        ing_code = values['-ING_CODE-']
        ing_qty = values['-ING_QTY-']
        if ing_code and ing_qty:
            # Get ingredient description from the main products dataframe
            ing_desc = df[df['Product Code'] == ing_code]['Description'].iloc[0] if not df[df['Product Code'] == ing_code].empty else 'Unknown'
            current_ingredients = window['-INGREDIENTS_TABLE-'].get()
            current_ingredients.append([ing_code, ing_desc, ing_qty, 'P/KG'])  # Added default Pack Deliver
            window['-INGREDIENTS_TABLE-'].update(current_ingredients)
            window['-ING_CODE-'].update('')
            window['-ING_QTY-'].update('')
    
    elif event == '-RECIPES_TABLE-':
        selected_rows = values['-RECIPES_TABLE-']
        if selected_rows:
            recipe = load_recipe_by_index(selected_rows[0])
            if recipe:
                window['-RECIPE_CODE-'].update(recipe['code'])
                window['-RECIPE_NAME-'].update(recipe['name'])
                window['-RECIPE_DEPT-'].update(recipe['department'])
                # Update ingredients table with all columns
                ingredients_data = [[ing[0], ing[1], ing[2]] for ing in recipe['ingredients']]
                window['-INGREDIENTS_TABLE-'].update(ingredients_data)
    
    elif event == 'Save Recipe':
        recipe_code = values['-RECIPE_CODE-']
        recipe_name = values['-RECIPE_NAME-']
        department = values['-RECIPE_DEPT-']
        ingredients = window['-INGREDIENTS_TABLE-'].get()
        
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
        window['-RECIPE_CODE-'].update('')
        window['-RECIPE_NAME-'].update('')
        window['-RECIPE_DEPT-'].update('')
        window['-INGREDIENTS_TABLE-'].update([])

def load_recipes_from_csv():
    """
    Load recipes from CSV file and store them in the database.
    Returns a dictionary of recipes organized by department.
    """
    recipes = {}
    try:
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        df = pd.read_csv('DEPARTMENTS - RECIPES - ALL DEPT..csv')
        
        # Initialize variables for tracking current recipe
        current_dept = None
        current_recipe = None
        current_recipe_id = None
        current_ingredients = []
        
        for _, row in df.iterrows():
            # If we have a new recipe (non-empty Final Product Code)
            if pd.notna(row['Final Product Code']):
                # Save previous recipe if exists
                if current_recipe is not None:
                    if current_dept not in recipes:
                        recipes[current_dept] = []
                    recipes[current_dept].append(current_recipe)
                
                # Start new recipe
                current_dept = row['Department']
                current_recipe = {
                    'code': str(row['Final Product Code']),
                    'name': row['Final Product Name'],
                    'department': row['Department'],
                    'ingredients': []
                }
                
                # Insert or update recipe in database
                cursor.execute('''
                    INSERT OR REPLACE INTO recipes (code, name, department)
                    VALUES (?, ?, ?)
                ''', (current_recipe['code'], current_recipe['name'], current_recipe['department']))
                current_recipe_id = cursor.lastrowid
                
                # Clear old ingredients for this recipe
                cursor.execute('DELETE FROM recipe_ingredients WHERE recipe_id = ?', (current_recipe_id,))
                
                current_ingredients = []
            
            # Add ingredient to current recipe
            if pd.notna(row['Ingredient Prod Code']) and current_recipe_id is not None:
                ingredient = [
                    str(row['Ingredient Prod Code']),
                    str(row['Ingredient Description']),
                    float(row['Recipe']) if pd.notna(row['Recipe']) else 0,
                    str(row['Pack Deliver']) if pd.notna(row['Pack Deliver']) else 'P/KG'
                ]
                current_recipe['ingredients'].append(ingredient)
                
                # Add ingredient to database
                cursor.execute('''
                    INSERT INTO recipe_ingredients (recipe_id, ingredient_code, quantity, unit)
                    VALUES (?, ?, ?, ?)
                ''', (current_recipe_id, ingredient[0], ingredient[2], ingredient[3]))
                
                # Also ensure the ingredient exists in the ingredients table
                cursor.execute('''
                    INSERT OR IGNORE INTO ingredients (code, name, unit, department)
                    VALUES (?, ?, ?, ?)
                ''', (ingredient[0], ingredient[1], ingredient[3], current_dept))
        
        # Add the last recipe
        if current_recipe is not None:
            if current_dept not in recipes:
                recipes[current_dept] = []
            recipes[current_dept].append(current_recipe)
        
        conn.commit()
        conn.close()
            
    except Exception as e:
        print(f"Error loading recipes from CSV: {e}")
        return {}
    
    return recipes

def save_recipe(recipe):
    recipes = load_all_recipes()
    department = recipe['department']
    
    if department not in recipes:
        recipes[department] = []
    
    # Update existing recipe or add new one
    updated = False
    for i, existing_recipe in enumerate(recipes[department]):
        if existing_recipe['code'] == recipe['code']:
            recipes[department][i] = recipe
            updated = True
            break
    
    if not updated:
        recipes[department].append(recipe)
    
    # Convert to DataFrame format
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
    df = pd.DataFrame(rows)
    df.to_csv('DEPARTMENTS - RECIPES - ALL DEPT..csv', index=False)

def load_all_recipes():
    try:
        return load_recipes_from_csv()
    except Exception as e:
        print(f"Error loading recipes: {e}")
        return {}

def load_recipe_by_index(index):
    recipes = load_all_recipes()
    all_recipes = []
    for dept_recipes in recipes.values():
        all_recipes.extend(dept_recipes)
    
    if 0 <= index < len(all_recipes):
        return all_recipes[index]
    return None

def update_recipes_table(window):
    recipes = load_all_recipes()
    table_data = []
    for dept_recipes in recipes.values():
        for r in dept_recipes:
            table_data.append([r['code'], r['name'], r['department'], len(r['ingredients'])])
    window['-RECIPES_TABLE-'].update(table_data)

def handle_reports_events(event, values, window, inventory, auth_system):
    """Handle events in the Reports tab."""
    try:
        if event == '-GENERATE_REPORT-':
            print("DEBUG: Generate report button clicked")
            print(f"DEBUG: Current values: {values}")
            
            # Parse dates
            try:
                start_date = datetime.strptime(values['-START_DATE-'], '%Y-%m-%d')
                end_date = datetime.strptime(values['-END_DATE-'], '%Y-%m-%d')
                print(f"DEBUG: Parsed dates - Start: {start_date}, End: {end_date}")
            except ValueError as date_error:
                print(f"DEBUG: Date parsing error - {date_error}")
                sg.popup_error('Invalid date format. Please use YYYY-MM-DD', font=FONT_NORMAL)
                return

            # Get department filter
            department = values['-REPORT_DEPT-']
            product_code = values['-REPORT_PRODUCT_CODE-'].strip()
            print(f"DEBUG: Department filter: {department}")
            print(f"DEBUG: Product code filter: {product_code}")
            print(f"DEBUG: Inventory size: {len(inventory) if inventory else 'None'}")

            try:
                # Generate traceability report
                print("DEBUG: Calling generate_traceability_report")
                report_data = generate_traceability_report(inventory, start_date, end_date, auth_system)
                print(f"DEBUG: Report data generated, items: {len(report_data)}")

                # Apply filters
                if department != 'All':
                    report_data = [item for item in report_data if item.get('Department') == department]
                    print(f"DEBUG: After department filter: {len(report_data)} items")
                if product_code:
                    report_data = [item for item in report_data if product_code.lower() in item.get('Product Code', '').lower()]
                    print(f"DEBUG: After product code filter: {len(report_data)} items")

                # Store report data and dates for export
                window.user_data = {
                    'report_data': report_data,
                    'start_date': start_date,
                    'end_date': end_date
                }

                # Update table with report data
                table_data = []
                for item in report_data:
                    try:
                        temp_log = format_temperature_log(item.get('Temperature Log', []))
                        handling_history = '\n'.join(item.get('Handling History', [])) if isinstance(item.get('Handling History'), list) else item.get('Handling History', '')
                        
                        row_data = [
                            item.get('Product Code', ''),
                            item.get('Product Description', ''),
                            item.get('Supplier Batch No', ''),
                            item.get('Received Date', ''),
                            item.get('Status', ''),
                            temp_log,
                            handling_history
                        ]
                        table_data.append(row_data)
                    except Exception as row_error:
                        print(f"DEBUG: Error processing row - {row_error}")
                        print(f"DEBUG: Problematic item - {item}")
                        continue

                print(f"DEBUG: Final table data rows: {len(table_data)}")
                window['-REPORT_TABLE-'].update(values=table_data)
                print("DEBUG: Table updated successfully")

            except Exception as report_error:
                print(f"DEBUG: Error in report generation - {report_error}")
                sg.popup_error(f'Error generating report: {str(report_error)}', font=FONT_NORMAL)
                return

        elif event == '-REPORT_TABLE-':
            if len(values['-REPORT_TABLE-']) > 0:
                selected_row = values['-REPORT_TABLE-'][0]
                print(f"DEBUG: Selected row index: {selected_row}")
                show_detailed_traceability(inventory[selected_row], auth_system)

        elif event == '-SAVE_PDF-':
            if not hasattr(window, 'user_data') or 'report_data' not in window.user_data:
                print("DEBUG: No report data available for PDF export")
                sg.popup_error('Please generate a report first', font=FONT_NORMAL)
                return
                
            save_path = sg.popup_get_file('Save PDF Report As', save_as=True, 
                                        file_types=(("PDF Files", "*.pdf"),), 
                                        default_extension=".pdf")
            if save_path:
                success = save_report_as_pdf(
                    save_path,
                    window.user_data['report_data'],
                    "Traceability Report",
                    window.user_data['start_date'],
                    window.user_data['end_date'],
                    auth_system
                )
                if success:
                    sg.popup('Success', 'Report saved successfully!', font=FONT_NORMAL)

        elif event == '-SAVE_CSV-':
            if 'report_data' not in locals():
                print("DEBUG: No report data available for CSV export")
                sg.popup_error('Please generate a report first', font=FONT_NORMAL)
                return
                
            save_path = sg.popup_get_file('Save CSV Report As', save_as=True, 
                                        file_types=(("CSV Files", "*.csv"),), 
                                        default_extension=".csv")
            if save_path:
                save_report_as_csv(save_path, report_data, "Traceability Report", window.user_data['start_date'], window.user_data['end_date'], auth_system)
                sg.popup('Success', 'Report saved successfully!', font=FONT_NORMAL)

    except Exception as e:
        print(f"DEBUG: Critical error in handle_reports_events - {e}")
        sg.popup_error(f'Error handling report event: {str(e)}', font=FONT_NORMAL)
        logging.error(f'Error in handle_reports_events: {str(e)}', exc_info=True)

def generate_traceability_report(inventory, start_date, end_date, auth_system):
    """
    Generate a traceability report for items within the specified date range.
    """
    print(f"DEBUG: Starting report generation with date range: {start_date} to {end_date}")
    print(f"DEBUG: Inventory type: {type(inventory)}")
    print(f"DEBUG: Inventory size: {len(inventory) if inventory else 'None'}")
    print("DEBUG: First few inventory items:")
    for i, item in enumerate(inventory[:3]):  # Print first 3 items for inspection
        print(f"DEBUG: Item {i}:")
        print(f"  - Product Code: {item.get('Product Code')}")
        print(f"  - Description: {item.get('Product Description')}")
        print(f"  - Delivery Date: {item.get('Delivery Date')}")
        print(f"  - All keys: {list(item.keys())}")
    
    report_data = []
    
    if not inventory:
        print("DEBUG: Inventory is empty or None")
        return report_data
        
    for index, item in enumerate(inventory):
        try:
            print(f"\nDEBUG: Processing item {index}: {item.get('Product Code', 'No Code')}")
            delivery_date_str = item.get('Delivery Date', '')
            print(f"DEBUG: Delivery date string: {delivery_date_str}")
            
            if not delivery_date_str:
                print(f"DEBUG: No delivery date for item {index}")
                continue
                
            try:
                # Try different datetime formats with time components
                try:
                    delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d %H:%M')
                    except ValueError:
                        try:
                            delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d')
                        except ValueError:
                            print(f"DEBUG: Could not parse date {delivery_date_str} in any format")
                            continue
                
                print(f"DEBUG: Parsed delivery date: {delivery_date}")
                
                # Compare only the date parts
                delivery_date = delivery_date.replace(hour=0, minute=0, second=0, microsecond=0)
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                
                print(f"DEBUG: Comparing dates: {start_date} <= {delivery_date} <= {end_date}")
                print(f"DEBUG: Date comparison result: {start_date <= delivery_date <= end_date}")
                
            except ValueError as date_error:
                print(f"DEBUG: Date parsing error for item {index} - {date_error}")
                continue
                
            if start_date <= delivery_date <= end_date:
                print(f"DEBUG: Item {index} is within date range")
                
                # Parse handling history for food handler names
                handling_history = item.get('Handling History', [])
                if isinstance(handling_history, str):
                    handling_history = handling_history.split('\n') if handling_history else []
                
                food_handlers = []
                for entry in handling_history:
                    if 'handled by' in entry.lower():
                        handler = entry.split('handled by')[-1].strip()
                        food_handlers.append(handler)
                
                # Create report item with audit schema fields
                report_item = {
                    'Product Code': item.get('Product Code', ''),
                    'Product Description': item.get('Product Description', ''),
                    'Product Name': item.get('Product Description', ''),  # For audit schema
                    'Supplier Batch No': item.get('Supplier Batch No', ''),
                    'Packaging Batch Code': item.get('Supplier Batch No', ''),  # For audit schema
                    'Received Date': delivery_date_str,
                    'Sell By Date': item.get('Sell By Date', ''),
                    'Status': item.get('Status', ''),
                    'Department': item.get('Department', ''),
                    'Department Manager': item.get('Department Manager', ''),
                    'Food Handler Names': food_handlers,
                    'Temperature Log': item.get('Temperature Log', []),
                    'Handling History': handling_history,
                    'Received By': item.get('Received By', ''),
                    'Processed By': item.get('Processed By', ''),
                    'Processing Date': item.get('Processing Date', ''),
                    'Tracking ID': item.get('Tracking ID', '')
                }
                
                # Add packaging information if available
                packaging_info = {
                    'Supplier Name': item.get('Supplier Name', ''),
                    'Supplier Address': item.get('Supplier Address', ''),
                    'Packaging Type': item.get('Packaging Type', ''),
                    'Quantity Received': item.get('Quantity', ''),
                    'Unit': item.get('Unit', '')
                }
                report_item['Packaging Info'] = packaging_info
                
                report_data.append(report_item)
                print(f"DEBUG: Added item to report")
                
        except Exception as e:
            print(f"DEBUG: Error processing item {index} - {e}")
            continue
            
    print(f"DEBUG: Final report contains {len(report_data)} items")
    return report_data

def show_detailed_traceability(product, auth_system):
    """Show detailed traceability information for a product."""
    if not product:
        return

    layout = [
        [sg.Text('Product Traceability Details', font=FONT_HEADER, justification='center')],
        [sg.Frame('Product Information', [
            [sg.Text(f"Product Code: {product.get('Product Code', 'N/A')}")],
            [sg.Text(f"Description: {product.get('Product Description', 'N/A')}")],
            [sg.Text(f"Batch Number: {product.get('Supplier Batch No', 'N/A')}")],
            [sg.Text(f"Sell by Date: {product.get('Sell By Date', 'N/A')}")],
        ])],
        [sg.Frame('Temperature History', [
            [sg.Multiline(format_temperature_log(product.get('Temperature Log', [])),
                         size=(50, 5), disabled=True, font=FONT_NORMAL)]
        ])],
        [sg.Frame('Handling History', [
            [sg.Multiline('\n'.join(product.get('Handling History', [])) if isinstance(product.get('Handling History'), list)
                         else product.get('Handling History', 'No handling history available'),
                         size=(50, 8), disabled=True, font=FONT_NORMAL)]
        ])],
        [sg.Button('Close', key='-CLOSE-', button_color=(COLORS['text'], COLORS['secondary']), font=FONT_NORMAL)]
    ]

    window = sg.Window('Product Traceability', layout, finalize=True, modal=True)
    
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, '-CLOSE-'):
            break
    
    window.close()

def create_reports_tab():
    today = datetime.now()
    layout = [
        [sg.Text('Traceability Report', font=FONT_HEADER, justification='center', expand_x=True)],
        [sg.Frame('Report Options', [
            [sg.Text('Date Range:', font=FONT_NORMAL)],
            [sg.Text('From:', font=FONT_NORMAL), 
             sg.Input(key='-START_DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d'), font=FONT_NORMAL),
             sg.CalendarButton('Choose', target='-START_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['primary']), font=FONT_NORMAL)],
            [sg.Text('To:', font=FONT_NORMAL), 
             sg.Input(key='-END_DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d'), font=FONT_NORMAL),
             sg.CalendarButton('Choose', target='-END_DATE-', format='%Y-%m-%d',
                             button_color=(COLORS['text'], COLORS['primary']), font=FONT_NORMAL)],
            [sg.Text('Department:', font=FONT_NORMAL),
             sg.Combo(['All', 'Butchery', 'Bakery', 'HMR'], default_value='All', key='-REPORT_DEPT-', 
                     size=(20,1), font=FONT_NORMAL)],
            [sg.Text('Product Code:', font=FONT_NORMAL), sg.Input(key='-REPORT_PRODUCT_CODE-', size=(20,1), font=FONT_NORMAL)],
            [sg.Button('Generate Report', key='-GENERATE_REPORT-', 
                      button_color=(COLORS['text'], COLORS['primary']), font=FONT_NORMAL)]
        ])],
        [sg.Frame('Report Preview', [
            [sg.Table(
                values=[], 
                headings=['Product Code', 'Description', 'Batch No', 'Received Date', 'Status', 
                         'Temperature Log', 'Handling History'],
                key='-REPORT_TABLE-',
                auto_size_columns=True,
                enable_events=True,
                num_rows=15,
                font=FONT_NORMAL
            )]
        ])],
        [sg.Frame('Export Options', [
            [sg.Button('Save as PDF', key='-SAVE_PDF-', button_color=(COLORS['text'], COLORS['secondary']), font=FONT_NORMAL),
             sg.Button('Save as CSV', key='-SAVE_CSV-', button_color=(COLORS['text'], COLORS['secondary']), font=FONT_NORMAL)]
        ])]
    ]
    return layout

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
    # Filter for processed items only
    processed_items = [item for item in inventory if item.get('Status') == 'Processed']
    
    # Update table with processed items
    processed_data = [
        [item['Product Code'], 
         item['Product Description'], 
         item['Quantity'], 
         item['Unit'],
         item.get('Supplier Batch No', ''),
         item.get('Sell By Date', ''),
         item.get('Processing Date', ''),
         item.get('Processed By', '')] for item in processed_items
    ]
    
    # Get currently displayed data
    current_data = window['-PROCESSED_TABLE-'].get()
    
    # Only update if the data is different
    if current_data != processed_data:
        window['-PROCESSED_TABLE-'].update(processed_data)

def refresh_display(window, inventory, auth_system):
    """
    Safely refresh the display without modifying processed product data.
    Only updates the visual representation of data that hasn't been processed.
    """
    # Get current user's info
    current_user = auth_system.get_current_user_info()
    if current_user is None:
        return False
        
    try:
        # Get fresh inventory data for the department
        fresh_inventory = get_department_inventory(current_user['department'])
        if fresh_inventory is None:
            fresh_inventory = []
            
        # Keep track of processed items from current inventory
        processed_items = [item for item in inventory if item.get('Status') == 'Processed']
        
        # Create a new inventory list with both processed and fresh items
        new_inventory = processed_items + fresh_inventory
        
        # Sort inventory by received date (newest first)
        new_inventory.sort(key=lambda x: datetime.strptime(x.get('Received Date', '1900-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S'), reverse=True)
        
        # Clear and update the inventory list
        inventory.clear()
        inventory.extend(new_inventory)
        
        # Update both tables
        update_inventory_table(window, inventory)
        update_processed_table(window, inventory)
        
        return True
        
    except Exception as e:
        sg.popup_error('Database Error', f'Error refreshing data: {str(e)}')
        return False

def show_login_window(auth_system):
    """Show login window and handle authentication."""
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

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            window.close()
            return False
            
        if event == 'Login':
            username = values['-USERNAME-']
            password = values['-PASSWORD-']
            
            if auth_system.login(username, password):
                window.close()
                return True
            else:
                sg.popup_error('Invalid username or password', font=FONT_NORMAL)
                
    window.close()
    return False

def record_temperature_popup():
    """Show temperature recording popup window."""
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

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            window.close()
            return None
            
        if event == 'Submit':
            try:
                temp = float(values['-TEMP-'])
                if -50 <= temp <= 100:  # Reasonable temperature range
                    window.close()
                    return {
                        'temperature': temp,
                        'location': values['-LOCATION-'],
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                else:
                    sg.popup_error('Please enter a valid temperature between -50°C and 100°C', 
                                 font=FONT_NORMAL)
            except ValueError:
                sg.popup_error('Please enter a valid number for temperature', 
                             font=FONT_NORMAL)
                
    window.close()
    return None

def generate_and_show_barcode(item):
     """Generate and display a barcode for the given item."""
     # Create a combined identifier combining product info
     timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
     combined_batch = f"{item['Product Code']}-{item['Supplier Batch No']}-{timestamp}"
    
     try:
         # Generate barcode image
         barcode_data = generate_barcode(combined_batch)
         if not barcode_data:
             sg.popup_error('Failed to generate barcode', font=FONT_NORMAL)
             return None
            
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
        
         while True:
             event, values = window.read()
             if event in (sg.WIN_CLOSED, 'Close'):
                 window.close()
                 return None
                
             if event == 'Save Barcode':
                 save_path = sg.popup_get_file(
                     'Save Barcode As...', 
                     save_as=True, 
                     default_extension='.png',
                     file_types=(("PNG Files", "*.png"),),
                     font=FONT_NORMAL
                 )
                 if save_path:
                     try:
                         save_barcode(barcode_data, item)
                         sg.popup('Barcode saved successfully!', font=FONT_NORMAL)
                     except Exception as e:
                         sg.popup_error(f'Error saving barcode: {str(e)}', font=FONT_NORMAL)
                        
         window.close()
         return None
        
     except Exception as e:
         sg.popup_error(f'Error generating barcode: {str(e)}', font=FONT_NORMAL)
         return None

def save_barcode(barcode_data, item):
     """Save the barcode image and update the database with barcode information."""
     try:
         # Generate a unique filename based on item details
         timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
         default_filename = f"barcode_{item['Product Code']}_{timestamp}.png"
        
         # Get save location from user
         save_path = sg.popup_get_file('Save Barcode As', save_as=True, 
                                       file_types=(("PNG Files", "*.png"),),
                                       default_extension='.png',
                                       default_path=default_filename,
                                       font=FONT_NORMAL)
         if save_path:
             # Ensure .png extension
             if not save_path.lower().endswith('.png'):
                 save_path += '.png'
            
             # Save the barcode image
             with open(save_path, 'wb') as f:
                 f.write(barcode_data)
            
             # Convert barcode data to base64 for database storage
             barcode_base64 = base64.b64encode(barcode_data).decode()
        
             # Generate tracking ID
             tracking_id = f"{item['Product Code']}-{item['Supplier Batch No']}-{timestamp}"
        
             # Update database
             conn = sqlite3.connect('spatrac.db')
             cursor = conn.cursor()
        
             cursor.execute('''
                 UPDATE received_products 
                 SET tracking_id = ?, barcode_image = ?
                 WHERE product_code = ? AND supplier_batch = ? AND status = 'Active'
             ''', (tracking_id, barcode_base64, item['Product Code'], item['Supplier Batch No']))
        
             conn.commit()
             conn.close()
        
             # Update the item dictionary
             item['tracking_id'] = tracking_id
             item['barcode_image'] = barcode_base64
        
             return True
        
     except Exception as e:
         sg.popup_error(f'Error saving barcode: {str(e)}', font=FONT_NORMAL)
         return False

def save_as_pdf(report_data, filename):
    """
    Save report data as PDF.
    Args:
        report_data: List of dictionaries containing report data
        filename: Output PDF filename
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=10)
        
        # Define column headers and widths
        headers = ['Product Code', 'Description', 'Batch No', 'Received Date', 'Status', 'Department']
        col_widths = [30, 60, 30, 30, 20, 20]
        
        # Calculate line height
        line_height = pdf.font_size * 1.5
        
        # Draw headers
        x_pos = pdf.l_margin
        for i, header in enumerate(headers):
            pdf.set_x(x_pos)
            pdf.cell(col_widths[i], line_height, header, border=1)
            x_pos += col_widths[i]
        pdf.ln()
        
        # Draw data rows
        for item in report_data:
            x_pos = pdf.l_margin
            max_height = line_height
            
            # Calculate maximum height needed for this row
            for i, header in enumerate(headers):
                if header == 'Product Code':
                    content = str(item.get('Product Code', ''))
                elif header == 'Description':
                    content = str(item.get('Product Description', ''))
                elif header == 'Batch No':
                    content = str(item.get('Supplier Batch No', ''))
                elif header == 'Received Date':
                    content = str(item.get('Received Date', ''))
                elif header == 'Status':
                    content = str(item.get('Status', ''))
                elif header == 'Department':
                    content = str(item.get('Department', ''))
                    
                # Get height needed for this content
                content_width = pdf.get_string_width(content)
                needed_height = (content_width / col_widths[i] + 1) * line_height
                max_height = max(max_height, needed_height)
            
            # Draw the row with calculated height
            x_pos = pdf.l_margin
            for i, header in enumerate(headers):
                if header == 'Product Code':
                    content = str(item.get('Product Code', ''))
                elif header == 'Description':
                    content = str(item.get('Product Description', ''))
                elif header == 'Batch No':
                    content = str(item.get('Supplier Batch No', ''))
                elif header == 'Received Date':
                    content = str(item.get('Received Date', ''))
                elif header == 'Status':
                    content = str(item.get('Status', ''))
                elif header == 'Department':
                    content = str(item.get('Department', ''))
                    
                pdf.set_x(x_pos)
                pdf.multi_cell(col_widths[i], line_height, content, border=1)
                x_pos += col_widths[i]
                
                # Move back up to stay on the same line
                pdf.set_y(pdf.get_y() - max_height)
            
            # Move to next line after drawing the row
            pdf.set_y(pdf.get_y() + max_height)
        
        pdf.output(filename)
        return True
        
    except Exception as e:
        print(f"DEBUG: Error saving PDF: {str(e)}")
        sg.popup_error(f'Error saving PDF: {str(e)}', font=FONT_NORMAL)
        return False

def save_as_csv(report, filename):
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Date', 'Product', 'Current Dept', 'Quantity', 'Status', 'Batch', 'Description', 'Processed By', 'Processing Date'])
        writer.writerows(report)

def initialize_database():
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    # First, create a temporary table to store existing data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_recipe_ingredients AS
        SELECT MIN(id) as id, recipe_id, ingredient_code, quantity, unit
        FROM recipe_ingredients
        GROUP BY recipe_id, ingredient_code
    ''')
    
    # Drop the existing table
    cursor.execute('DROP TABLE IF EXISTS recipe_ingredients')
    
    # Create the table with unique constraint
    cursor.execute('''
        CREATE TABLE recipe_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER,
            ingredient_code TEXT,
            quantity REAL,
            unit TEXT,
            FOREIGN KEY (recipe_id) REFERENCES recipes (id),
            FOREIGN KEY (ingredient_code) REFERENCES ingredients (code),
            UNIQUE(recipe_id, ingredient_code)
        )
    ''')
    
    # Restore the data from temporary table
    cursor.execute('''
        INSERT INTO recipe_ingredients (id, recipe_id, ingredient_code, quantity, unit)
        SELECT * FROM temp_recipe_ingredients
    ''')
    
    # Drop the temporary table
    cursor.execute('DROP TABLE IF EXISTS temp_recipe_ingredients')
    
    # Create other tables as before...
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
            tracking_id TEXT,
            barcode_image TEXT,
            department_manager TEXT,
            supplier_name TEXT,
            supplier_address TEXT,
            country_of_origin TEXT,
            packaging_type TEXT,
            food_handler_name TEXT,
            packaging_batch_code TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE,
            unit TEXT,
            department TEXT,
            description TEXT,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            department TEXT,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if columns exist and add them if they don't
    cursor.execute("PRAGMA table_info(received_products)")
    columns = [info[1] for info in cursor.fetchall()]
    
    required_columns = {
        'status': 'TEXT DEFAULT "Active"',
        'handling_history': 'TEXT DEFAULT ""',
        'temperature_log': 'TEXT DEFAULT ""',
        'processed_by': 'TEXT',
        'processing_date': 'TEXT',
        'tracking_id': 'TEXT',
        'barcode_image': 'TEXT',
        'department_manager': 'TEXT',
        'supplier_name': 'TEXT',
        'supplier_address': 'TEXT',
        'country_of_origin': 'TEXT',
        'packaging_type': 'TEXT',
        'food_handler_name': 'TEXT',
        'packaging_batch_code': 'TEXT'
    }
    
    for col_name, col_type in required_columns.items():
        if col_name not in columns:
            cursor.execute(f'ALTER TABLE received_products ADD COLUMN {col_name} {col_type}')
    
    conn.commit()
    conn.close()

def add_received_product(product, auth_system, window=None):
    """Add a new product to the received products database."""
    try:
        user_info = auth_system.get_current_user_info()
        if not user_info:
            return False
            
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Initialize lists for tracking
        if 'Temperature Log' not in product or isinstance(product['Temperature Log'], str):
            product['Temperature Log'] = []
        if 'Handling History' not in product or isinstance(product['Handling History'], str):
            product['Handling History'] = []
            
        # Add receiving history
        product['Handling History'].append(
            f"Received on {current_time} by {user_info['username']} ({user_info['role']} - {user_info['department']})"
        )
        
        # Add receiving information
        product['Received Date'] = current_time
        product['Received By'] = user_info['username']
        product['Status'] = 'Active'
        product['Department'] = user_info['department']  # Add department information
        
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO received_products (
                product_code, description, quantity, unit,
                supplier_batch, sell_by_date, status,
                received_date, received_by, handling_history,
                temperature_log, department, tracking_id,
                barcode_image, department_manager, supplier_name, supplier_address, country_of_origin, packaging_type, food_handler_name, packaging_batch_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product['Product Code'],
            product['Product Description'],
            product['Quantity'],
            product['Unit'],
            product['Supplier Batch No'],  # Changed from 'Supplier Batch' to 'Supplier Batch No'
            product['Sell By Date'],
            'Active',
            product['Received Date'],
            product['Received By'],
            json.dumps(product['Handling History']),
            json.dumps(product['Temperature Log']),
            product['Department'],
            str(uuid.uuid4()),  # tracking_id
            '',  # barcode_image
            user_info['username'],  # department_manager
            'Supplier Name',  # supplier_name
            'Supplier Address',  # supplier_address
            'Country of Origin',  # country_of_origin
            'Packaging Type',  # packaging_type
            user_info['username'],  # food_handler_name
            product['Supplier Batch No']  # packaging_batch_code
        ))
        
        # Get the ID of the newly inserted product
        product_id = cursor.lastrowid
        conn.commit()
        
        # Find and notify about matching recipes
        matching_recipes = find_matching_recipes(product['Product Code'])
        if matching_recipes:
            notify_matching_recipes(product, matching_recipes, window)
        
        conn.close()
        return True, product_id
    except Exception as e:
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
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT product_code, description, quantity, unit, supplier_batch, 
                   sell_by_date, received_date, received_by, status, department,
                   COALESCE(handling_history, '[]') as handling_history,
                   COALESCE(temperature_log, '[]') as temperature_log,
                   COALESCE(tracking_id, '') as tracking_id,
                   COALESCE(barcode_image, '') as barcode_image,
                   COALESCE(processed_by, '') as processed_by,
                   COALESCE(processing_date, '') as processing_date,
                   COALESCE(department_manager, '') as department_manager,
                   COALESCE(supplier_name, '') as supplier_name,
                   COALESCE(supplier_address, '') as supplier_address,
                   COALESCE(country_of_origin, '') as country_of_origin,
                   COALESCE(packaging_type, '') as packaging_type,
                   COALESCE(food_handler_name, '') as food_handler_name,
                   COALESCE(packaging_batch_code, '') as packaging_batch_code
            FROM received_products
            WHERE department = ? AND status = 'Active'
            ORDER BY received_date DESC
        ''', (department,))
        
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
            
            # Parse JSON strings for lists
            try:
                item['Handling History'] = json.loads(item.pop('handling_history'))
            except json.JSONDecodeError:
                item['Handling History'] = []
                
            try:
                item['Temperature Log'] = json.loads(item.pop('temperature_log'))
            except json.JSONDecodeError:
                item['Temperature Log'] = []
            
            # Add tracking ID if available
            tracking_id = item.pop('tracking_id', '')
            if tracking_id:
                item['tracking_id'] = tracking_id
            
            # Add barcode data if available
            barcode_image = item.pop('barcode_image', '')
            if barcode_image:
                item['barcode_image'] = barcode_image
            
            # Add processing information if available
            item['Processed By'] = item.pop('processed_by', '')
            item['Processing Date'] = item.pop('processing_date', '')
            
            # Add additional fields
            item['Department Manager'] = item.pop('department_manager', '')
            item['Supplier Name'] = item.pop('supplier_name', '')
            item['Supplier Address'] = item.pop('supplier_address', '')
            item['Country of Origin'] = item.pop('country_of_origin', '')
            item['Packaging Type'] = item.pop('packaging_type', '')
            item['Food Handler Name'] = item.pop('food_handler_name', '')
            item['Packaging Batch Code'] = item.pop('packaging_batch_code', '')
            
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

def create_database_management_tab():
    today = datetime.now()
    layout = [
        [sg.Text('Database Management', font=FONT_HEADER, justification='center', expand_x=True)],
        [sg.Frame('Search Records', [
            [sg.Text('Date Range:', font=FONT_NORMAL)],
            [sg.Text('From:', font=FONT_NORMAL), 
             sg.Input(key='-DB-START-DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d'), enable_events=True),
             sg.CalendarButton('Choose', target='-DB-START-DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['primary']), key='-DB-START-CAL-'),
             sg.Text('To:', font=FONT_NORMAL), 
             sg.Input(key='-DB-END-DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d'), enable_events=True),
             sg.CalendarButton('Choose', target='-DB-END-DATE-', format='%Y-%m-%d',
                             button_color=(COLORS['text'], COLORS['primary']), key='-DB-END-CAL-')],
            [sg.Text('Department:', font=FONT_NORMAL),
             sg.Combo(['All', 'Butchery', 'Bakery', 'HMR'], default_value='All', key='-DB-DEPT-', size=(20,1))],
            [sg.Text('Status:', font=FONT_NORMAL),
             sg.Combo(['All', 'Active', 'Processed'], default_value='All', key='-DB-STATUS-', size=(20,1))],
            [sg.Text('Product Code:', font=FONT_NORMAL), sg.Input(key='-DB-PRODUCT-CODE-', size=(20,1))],
            [sg.Button('Search', key='-DB-SEARCH-', button_color=(COLORS['text'], COLORS['primary']))]
        ])],
        [sg.Frame('Results', [
            [sg.Table(values=[], 
                     headings=['Date', 'Product', 'Current Dept', 'Quantity', 'Status', 'Batch', 'Description', 'Processed By', 'Processing Date'],
                     key='-DB-TABLE-',
                     auto_size_columns=True,
                     enable_events=True,
                     num_rows=10)]
        ])],
        [sg.Frame('Actions', [
            [sg.Button('Export to CSV', key='-DB-EXPORT-CSV-', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Export to PDF', key='-DB-EXPORT-PDF-', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('View Details', key='-DB-VIEW-DETAILS-', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Delete All Active Products', key='-DB-DELETE-ALL-', button_color=(COLORS['text'], COLORS['danger']))]])],
    ]
    return sg.Tab('Database Management', layout, key='-DATABASE-TAB-')

def handle_database_management_events(event, values, window, inventory, auth_system):
    if not auth_system.is_manager():
        sg.popup_error('Access Denied', 'Only managers can access database management features.')
        return

    if event == '-DB-SEARCH-':
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
                    tracking_id,
                    barcode_image,
                    department_manager,
                    supplier_name,
                    supplier_address,
                    country_of_origin,
                    packaging_type,
                    food_handler_name,
                    packaging_batch_code
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
                
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Format results for display
            formatted_results = []
            for row in results:
                formatted_row = list(row[:9])  # Get all columns except handling_history, tracking_id, barcode_image
                formatted_results.append(formatted_row)
                
            window['-DB-TABLE-'].update(formatted_results)
            conn.close()
        except Exception as e:
            sg.popup_error('Database Error', f'Error searching database: {str(e)}')

    elif event == '-DB-EXPORT-CSV-':
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
                sg.popup('Report saved successfully!', title='Success')
            except Exception as e:
                sg.popup_error('Export Error', f'Error saving CSV: {str(e)}')

    elif event == '-DB-EXPORT-PDF-':
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
                pdf.cell(0, 10, txt=f"Date Range: {values['-DB-START-DATE-']} to {values['-DB-END-DATE-']}", ln=True)
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
        with open(f'data/{department.lower()}_final_products.csv', 'r') as file:
            reader = csv.DictReader(file)
            return list(reader)
    except FileNotFoundError:
        return []    

def create_relationships_between_ingredients_and_received_products(conn):
    """
    Create relationships between ingredients and received products.
    """
    try:
        # Fetch ingredients and received products
        ingredients = fetch_ingredients(conn)
        received_products = fetch_received_products(conn)
        
        relationships = []
        
        # Convert received_products to list of dicts if it's a DataFrame
        if isinstance(received_products, pd.DataFrame):
            received_products = received_products.to_dict('records')
            
        # Convert ingredients to list of dicts if it's a DataFrame
        if isinstance(ingredients, pd.DataFrame):
            ingredients = ingredients.to_dict('records')
        
        for received_product in received_products:
            for ingredient in ingredients:
                if received_product.get('Product Code') == ingredient.get('code'):
                    relationship = {
                        'ingredient_code': ingredient.get('code'),
                        'ingredient_name': ingredient.get('name'),
                        'received_product_code': received_product.get('Product Code'),
                        'received_product_desc': received_product.get('Product Description')
                    }
                    relationships.append(relationship)
        
        return relationships
        
    except Exception as e:
        print(f"Error creating relationships: {str(e)}")
        return []

def fetch_ingredients(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ingredients')
    ingredients_df = pd.DataFrame(cursor.fetchall())
    return ingredients_df

def fetch_received_products(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM received_products')
    received_products_df = pd.DataFrame(cursor.fetchall())
    return received_products_df

def add_ingredient(name, code, unit, department, description=''):
    """
    Add a new ingredient to the database.
    
    Args:
        name (str): Name of the ingredient
        code (str): Unique code for the ingredient
        unit (str): Unit of measurement
        department (str): Department the ingredient belongs to
        description (str, optional): Additional details about the ingredient
    
    Returns:
        bool: True if successful, False otherwise
        str: Success message or error message
    """
    try:
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO ingredients (name, code, unit, department, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, code, unit, department, description))
        
        conn.commit()
        conn.close()
        return True, "Ingredient added successfully"
    except sqlite3.IntegrityError:
        return False, f"Error: Ingredient code '{code}' already exists"
    except Exception as e:
        return False, f"Error adding ingredient: {str(e)}"

def find_matching_recipes(product_code):
    """
    Find all recipes that use a given product code as an ingredient.
    
    Args:
        product_code (str): The code of the received product
        
    Returns:
        list: List of recipe dictionaries that use this product
    """
    try:
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT r.id, r.code, r.name, r.department, ri.quantity, ri.unit
            FROM recipes r
            JOIN recipe_ingredients ri ON r.id = ri.recipe_id
            WHERE ri.ingredient_code = ?
        ''', (product_code,))
        
        matching_recipes = []
        for row in cursor.fetchall():
            recipe = {
                'id': row[0],
                'code': row[1],
                'name': row[2],
                'department': row[3],
                'ingredient_quantity': row[4],
                'ingredient_unit': row[5]
            }
            matching_recipes.append(recipe)
        
        conn.close()
        return matching_recipes
    except Exception as e:
        print(f"Error finding matching recipes: {e}")
        return []

def notify_matching_recipes(product, matching_recipes, window=None):
    """
    Notify about matching recipes for a received product.
    
    Args:
        product (dict): The received product information
        matching_recipes (list): List of recipes that use this product
        window (PySimpleGUI.Window, optional): Window to update if provided
    """
    if not matching_recipes:
        return
    
    notification = f"Product {product['Product Code']} is used in the following recipes:\n\n"
    for recipe in matching_recipes:
        notification += f"- {recipe['name']} (Code: {recipe['code']}) in {recipe['department']}\n"
        notification += f"  Required: {recipe['ingredient_quantity']} {recipe['ingredient_unit']}\n"
    
    if window:
        sg.popup("Recipe Matches Found", notification, title="Recipe Information")
    else:
        print(notification)

def generate_traceability_report(inventory, start_date, end_date, auth_system):
    """
    Generate a traceability report for items within the specified date range.
    """
    print(f"DEBUG: Starting report generation with date range: {start_date} to {end_date}")
    print(f"DEBUG: Inventory type: {type(inventory)}")
    print(f"DEBUG: Inventory size: {len(inventory) if inventory else 'None'}")
    print("DEBUG: First few inventory items:")
    for i, item in enumerate(inventory[:3]):  # Print first 3 items for inspection
        print(f"DEBUG: Item {i}:")
        print(f"  - Product Code: {item.get('Product Code')}")
        print(f"  - Description: {item.get('Product Description')}")
        print(f"  - Delivery Date: {item.get('Delivery Date')}")
        print(f"  - All keys: {list(item.keys())}")
    
    report_data = []
    
    if not inventory:
        print("DEBUG: Inventory is empty or None")
        return report_data
        
    for index, item in enumerate(inventory):
        try:
            print(f"\nDEBUG: Processing item {index}: {item.get('Product Code', 'No Code')}")
            delivery_date_str = item.get('Delivery Date', '')
            print(f"DEBUG: Delivery date string: {delivery_date_str}")
            
            if not delivery_date_str:
                print(f"DEBUG: No delivery date for item {index}")
                continue
                
            try:
                # Try different datetime formats with time components
                try:
                    delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d %H:%M')
                    except ValueError:
                        try:
                            delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d')
                        except ValueError:
                            print(f"DEBUG: Could not parse date {delivery_date_str} in any format")
                            continue
                
                print(f"DEBUG: Parsed delivery date: {delivery_date}")
                
                # Compare only the date parts
                delivery_date = delivery_date.replace(hour=0, minute=0, second=0, microsecond=0)
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                
                print(f"DEBUG: Comparing dates: {start_date} <= {delivery_date} <= {end_date}")
                print(f"DEBUG: Date comparison result: {start_date <= delivery_date <= end_date}")
                
            except ValueError as date_error:
                print(f"DEBUG: Date parsing error for item {index} - {date_error}")
                continue
                
            if start_date <= delivery_date <= end_date:
                print(f"DEBUG: Item {index} is within date range")
                
                # Parse handling history for food handler names
                handling_history = item.get('Handling History', [])
                if isinstance(handling_history, str):
                    handling_history = handling_history.split('\n') if handling_history else []
                
                food_handlers = []
                for entry in handling_history:
                    if 'handled by' in entry.lower():
                        handler = entry.split('handled by')[-1].strip()
                        food_handlers.append(handler)
                
                # Create report item with audit schema fields
                report_item = {
                    'Product Code': item.get('Product Code', ''),
                    'Product Description': item.get('Product Description', ''),
                    'Product Name': item.get('Product Description', ''),  # For audit schema
                    'Supplier Batch No': item.get('Supplier Batch No', ''),
                    'Packaging Batch Code': item.get('Supplier Batch No', ''),  # For audit schema
                    'Received Date': delivery_date_str,
                    'Sell By Date': item.get('Sell By Date', ''),
                    'Status': item.get('Status', ''),
                    'Department': item.get('Department', ''),
                    'Department Manager': item.get('Department Manager', ''),
                    'Food Handler Names': food_handlers,
                    'Temperature Log': item.get('Temperature Log', []),
                    'Handling History': handling_history,
                    'Received By': item.get('Received By', ''),
                    'Processed By': item.get('Processed By', ''),
                    'Processing Date': item.get('Processing Date', ''),
                    'Tracking ID': item.get('Tracking ID', '')
                }
                
                # Add packaging information if available
                packaging_info = {
                    'Supplier Name': item.get('Supplier Name', ''),
                    'Supplier Address': item.get('Supplier Address', ''),
                    'Packaging Type': item.get('Packaging Type', ''),
                    'Quantity Received': item.get('Quantity', ''),
                    'Unit': item.get('Unit', '')
                }
                report_item['Packaging Info'] = packaging_info
                
                report_data.append(report_item)
                print(f"DEBUG: Added item to report")
                
        except Exception as e:
            print(f"DEBUG: Error processing item {index} - {e}")
            continue
            
    print(f"DEBUG: Final report contains {len(report_data)} items")
    return report_data

def show_detailed_traceability(product, auth_system):
    """Show detailed traceability information for a product."""
    if not product:
        return

    layout = [
        [sg.Text('Product Traceability Details', font=FONT_HEADER, justification='center')],
        [sg.Frame('Product Information', [
            [sg.Text(f"Product Code: {product.get('Product Code', 'N/A')}")],
            [sg.Text(f"Description: {product.get('Product Description', 'N/A')}")],
            [sg.Text(f"Batch Number: {product.get('Supplier Batch No', 'N/A')}")],
            [sg.Text(f"Sell by Date: {product.get('Sell By Date', 'N/A')}")],
        ])],
        [sg.Frame('Temperature History', [
            [sg.Multiline(format_temperature_log(product.get('Temperature Log', [])),
                         size=(50, 5), disabled=True, font=FONT_NORMAL)]
        ])],
        [sg.Frame('Handling History', [
            [sg.Multiline('\n'.join(product.get('Handling History', [])) if isinstance(product.get('Handling History'), list)
                         else product.get('Handling History', 'No handling history available'),
                         size=(50, 8), disabled=True, font=FONT_NORMAL)]
        ])],
        [sg.Button('Close', key='-CLOSE-', button_color=(COLORS['text'], COLORS['secondary']), font=FONT_NORMAL)]
    ]

    window = sg.Window('Product Traceability', layout, finalize=True, modal=True)
    
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, '-CLOSE-'):
            break
    
    window.close()

def format_temperature_log(temp_log):
    """
    Format temperature log entries for display.
    
    Args:
        temp_log (list): List of temperature log entries
    
    Returns:
        str: Formatted temperature log string
    """
    if not temp_log:
        return ''
    
    formatted_log = []
    for entry in temp_log:
        if isinstance(entry, dict):
            timestamp = entry.get('timestamp', '')
            temperature = entry.get('temperature', '')
            formatted_log.append(f"{timestamp}: {temperature}°C")
    
    return '\n'.join(formatted_log)

def save_report_as_pdf(filename, report_data, title, start_date, end_date, auth_system):
    """
    Save a formatted report as PDF with headers and metadata.
    
    Args:
        filename: Output PDF filename
        report_data: List of dictionaries containing report data
        title: Report title
        start_date: Start date of the report period
        end_date: End date of the report period
        auth_system: Authentication system for user info
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Add report header
        pdf.set_font("Courier", 'B', size=16)
        pdf.cell(0, 10, txt=title, ln=True, align='C')
        
        # Add metadata
        pdf.set_font("Courier", size=10)
        pdf.cell(0, 5, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.cell(0, 5, txt=f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", ln=True)
        pdf.cell(0, 5, txt=f"Generated by: {auth_system.current_user}", ln=True)
        pdf.ln(5)
        
        # Process each item
        for item in report_data:
            # Product Information Section
            pdf.set_font("Courier", 'B', size=12)
            pdf.cell(0, 10, txt="Product Information", ln=True)
            pdf.set_font("Courier", size=10)
            
            info_lines = [
                f"Product Code: {item.get('Product Code', '')}",
                f"Product Name: {item.get('Product Name', '')}",
                f"Description: {item.get('Product Description', '')}",
                f"Department: {item.get('Department', '')}",
                f"Status: {item.get('Status', '')}",
                f"Tracking ID: {item.get('Tracking ID', '')}"
            ]
            
            for line in info_lines:
                pdf.cell(0, 5, txt=line, ln=True)
            
            # Dates and Batch Information
            pdf.ln(5)
            pdf.set_font("Courier", 'B', size=12)
            pdf.cell(0, 10, txt="Dates and Batch Information", ln=True)
            pdf.set_font("Courier", size=10)
            
            date_lines = [
                f"Received Date: {item.get('Received Date', '')}",
                f"Sell By Date: {item.get('Sell By Date', '')}",
                f"Processing Date: {item.get('Processing Date', '')}",
                f"Batch Number: {item.get('Supplier Batch No', '')}"
            ]
            
            for line in date_lines:
                pdf.cell(0, 5, txt=line, ln=True)
            
            # Personnel Information
            pdf.ln(5)
            pdf.set_font("Courier", 'B', size=12)
            pdf.cell(0, 10, txt="Personnel Information", ln=True)
            pdf.set_font("Courier", size=10)
            
            personnel_lines = [
                f"Department Manager: {item.get('Department Manager', '')}",
                f"Received By: {item.get('Received By', '')}",
                f"Processed By: {item.get('Processed By', '')}",
                f"Food Handlers: {', '.join(item.get('Food Handler Names', []))}"
            ]
            
            for line in personnel_lines:
                pdf.cell(0, 5, txt=line, ln=True)
            
            # Packaging Information
            pdf.ln(5)
            pdf.set_font("Courier", 'B', size=12)
            pdf.cell(0, 10, txt="Packaging Information", ln=True)
            pdf.set_font("Courier", size=10)
            
            packaging_info = item.get('Packaging Info', {})
            packaging_lines = [
                f"Supplier Name: {packaging_info.get('Supplier Name', '')}",
                f"Supplier Address: {packaging_info.get('Supplier Address', '')}",
                f"Packaging Type: {packaging_info.get('Packaging Type', '')}",
                f"Quantity Received: {packaging_info.get('Quantity Received', '')} {packaging_info.get('Unit', '')}"
            ]
            
            for line in packaging_lines:
                pdf.cell(0, 5, txt=line, ln=True)
            
            # Temperature Log
            if item.get('Temperature Log'):
                pdf.ln(5)
                pdf.set_font("Courier", 'B', size=12)
                pdf.cell(0, 10, txt="Temperature Log", ln=True)
                pdf.set_font("Courier", size=10)
                
                temp_log = item.get('Temperature Log', [])
                if isinstance(temp_log, str):
                    temp_log = temp_log.split('\n')
                for log in temp_log:
                    pdf.cell(0, 5, txt=log, ln=True)
            
            # Handling History
            if item.get('Handling History'):
                pdf.ln(5)
                pdf.set_font("Courier", 'B', size=12)
                pdf.cell(0, 10, txt="Handling History", ln=True)
                pdf.set_font("Courier", size=10)
                
                history = item.get('Handling History', [])
                if isinstance(history, str):
                    history = history.split('\n')
                for entry in history:
                    pdf.cell(0, 5, txt=entry, ln=True)
            
            # Add a separator between items
            pdf.cell(0, 5, txt="_" * 80, ln=True)
            pdf.ln(10)
        
        # Add footer
        pdf.ln(10)
        pdf.set_font("Courier", 'I', size=8)
        pdf.cell(0, 5, txt="Generated by SPATRAC - Traceability Management System", ln=True, align='C')
        
        pdf.output(filename)
        return True
        
    except Exception as e:
        print(f"DEBUG: Error saving PDF report: {str(e)}")
        sg.popup_error(f'Error saving PDF report: {str(e)}', font=FONT_NORMAL)
        return False

def save_report_as_pdf(filename, report_data, title, start_date, end_date, auth_system):
    """
    Save a formatted report as PDF with headers and metadata.
    
    Args:
        filename: Output PDF filename
        report_data: List of dictionaries containing report data
        title: Report title
        start_date: Start date of the report period
        end_date: End date of the report period
        auth_system: Authentication system for user info
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Add report header
        pdf.set_font("Courier", 'B', size=16)
        pdf.cell(0, 10, txt=title, ln=True, align='C')
        
        # Add metadata
        pdf.set_font("Courier", size=10)
        pdf.cell(0, 5, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.cell(0, 5, txt=f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", ln=True)
        pdf.cell(0, 5, txt=f"Generated by: {auth_system.current_user}", ln=True)
        pdf.ln(5)
        
        # Process each item
        for item in report_data:
            # Product Information Section
            pdf.set_font("Courier", 'B', size=12)
            pdf.cell(0, 10, txt="Product Information", ln=True)
            pdf.set_font("Courier", size=10)
            pdf.cell(0, 5, txt=f"Product Code: {item.get('Product Code', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Description: {item.get('Product Description', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Quantity: {item.get('Quantity', '')} {item.get('Unit', '')}", ln=True)
            pdf.ln(5)
            
            # Dates and Batch Information
            pdf.set_font("Courier", 'B', size=12)
            pdf.cell(0, 10, txt="Dates and Batch Information", ln=True)
            pdf.set_font("Courier", size=10)
            pdf.cell(0, 5, txt=f"Received Date: {item.get('Received Date', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Sell By Date: {item.get('Sell By Date', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Supplier Batch No: {item.get('Supplier Batch No', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Packaging Batch Code: {item.get('Packaging Batch Code', '')}", ln=True)
            pdf.ln(5)
            
            # Personnel Information
            pdf.set_font("Courier", 'B', size=12)
            pdf.cell(0, 10, txt="Personnel Information", ln=True)
            pdf.set_font("Courier", size=10)
            pdf.cell(0, 5, txt=f"Department: {item.get('Department', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Department Manager: {item.get('Department Manager', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Food Handler: {item.get('Food Handler Name', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Received By: {item.get('Received By', '')}", ln=True)
            if item.get('Processed By'):
                pdf.cell(0, 5, txt=f"Processed By: {item.get('Processed By', '')}", ln=True)
                pdf.cell(0, 5, txt=f"Processing Date: {item.get('Processing Date', '')}", ln=True)
            pdf.ln(5)
            
            # Supplier Information
            pdf.set_font("Courier", 'B', size=12)
            pdf.cell(0, 10, txt="Supplier Information", ln=True)
            pdf.set_font("Courier", size=10)
            pdf.cell(0, 5, txt=f"Supplier Name: {item.get('Supplier Name', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Supplier Address: {item.get('Supplier Address', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Country of Origin: {item.get('Country of Origin', '')}", ln=True)
            pdf.cell(0, 5, txt=f"Packaging Type: {item.get('Packaging Type', '')}", ln=True)
            pdf.ln(5)
            
            # Temperature Log
            if item.get('Temperature Log'):
                pdf.set_font("Courier", 'B', size=12)
                pdf.cell(0, 10, txt="Temperature Log", ln=True)
                pdf.set_font("Courier", size=10)
                
                temp_log = item.get('Temperature Log', [])
                if isinstance(temp_log, str):
                    temp_log = temp_log.split('\n')
                for log in temp_log:
                    pdf.cell(0, 5, txt=log, ln=True)
            
            # Handling History
            if item.get('Handling History'):
                pdf.set_font("Courier", 'B', size=12)
                pdf.cell(0, 10, txt="Handling History", ln=True)
                pdf.set_font("Courier", size=10)
                
                history = item.get('Handling History', [])
                if isinstance(history, str):
                    history = history.split('\n')
                for entry in history:
                    pdf.cell(0, 5, txt=entry, ln=True)
            
            # Add a separator between items
            pdf.cell(0, 5, txt="_" * 80, ln=True)
            pdf.ln(10)
        
        # Add footer
        pdf.ln(10)
        pdf.set_font("Courier", 'I', size=8)
        pdf.cell(0, 5, txt="Generated by SPATRAC - Traceability Management System", ln=True, align='C')
        
        pdf.output(filename)
        return True
        
    except Exception as e:
        print(f"DEBUG: Error saving PDF report: {str(e)}")
        sg.popup_error(f'Error saving PDF report: {str(e)}', font=FONT_NORMAL)
        return False

def remove_duplicate_recipe_ingredients():
    """
    Remove duplicate entries from recipe_ingredients table.
    Keeps the first occurrence of each recipe_id-ingredient_code combination.
    Returns the number of duplicates removed.
    """
    try:
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        # Create temporary table with unique combinations
        cursor.execute('''
            CREATE TEMPORARY TABLE temp_recipe_ingredients AS
            SELECT MIN(id) as id, recipe_id, ingredient_code, quantity, unit
            FROM recipe_ingredients
            GROUP BY recipe_id, ingredient_code
        ''')
        
        # Get count of duplicates that will be removed
        cursor.execute('''
            SELECT COUNT(*) FROM recipe_ingredients
            WHERE id NOT IN (SELECT id FROM temp_recipe_ingredients)
        ''')
        duplicate_count = cursor.fetchone()[0]
        
        # Delete all rows and reinsert only unique combinations
        cursor.execute('DELETE FROM recipe_ingredients')
        cursor.execute('''
            INSERT INTO recipe_ingredients (id, recipe_id, ingredient_code, quantity, unit)
            SELECT * FROM temp_recipe_ingredients
        ''')
        
        # Drop temporary table
        cursor.execute('DROP TABLE temp_recipe_ingredients')
        
        conn.commit()
        print(f"Removed {duplicate_count} duplicate recipe ingredients")
        return duplicate_count
        
    except sqlite3.Error as e:
        print(f"Database error removing duplicates: {e}")
        if 'conn' in locals():
            conn.rollback()
        return -1
    finally:
        if 'conn' in locals():
            conn.close()

def check_recipe_ingredient_duplicates():
    """
    Check for duplicate entries in recipe_ingredients table.
    Returns the count of duplicates found.
    """
    try:
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) - COUNT(DISTINCT recipe_id || '_' || ingredient_code)
            FROM recipe_ingredients
        ''')
        
        duplicate_count = cursor.fetchone()[0]
        return duplicate_count
        
    except sqlite3.Error as e:
        print(f"Database error checking duplicates: {e}")
        return -1
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    initialize_database()  # Initialize/update database schema
    file_paths = ['Butchery reports Big G.csv', 'Bakery Big G.csv', 'HMR Big G.csv']
    df = load_data(file_paths)
    create_gui(df)
    conn = sqlite3.connect('spatrac.db')
    relationships = create_relationships_between_ingredients_and_received_products(conn)
    print("Relationships between ingredients and received products:")
    print(relationships)