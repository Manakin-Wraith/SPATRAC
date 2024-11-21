import pandas as pd
import PySimpleGUI as sg
import csv
from fpdf import FPDF
from datetime import datetime
import barcode
from barcode import Code128
from barcode.writer import ImageWriter
import io
from PIL import Image
from auth_system import AuthSystem
import json
import sqlite3
import base64
import os

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
    'error': '#d93025'
}

# Load the data
def load_data(file_paths):
    dfs = []
    required_columns = [
        "Supp. Cd.", "Supplier Name", "Sub-Department", 
        "Supplier Product Code", "Product Code", "Product Description"
    ]
    
    for file_path in file_paths:
        df = pd.read_csv(file_path, encoding='iso-8859-1', sep=';')
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        df = df[required_columns]
        department = file_path.split()[0].lower()
        df['Department'] = department
        dfs.append(df)
    
    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df['unique_id'] = [f"row_{i}" for i in range(len(combined_df))]
    combined_df.set_index('unique_id', inplace=True, drop=False)
    
    return combined_df
    

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
def deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date, auth_system):
    product = df[df['Product Code'] == product_code].iloc[0]
    batch_lot = f'LOT-{datetime.now().strftime("%Y%m%d")}-{product_code}'
    current_user = auth_system.get_current_user_info()
    delivery_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create the initial product dictionary with consistent key names
    product_dict = {
        'Product Code': product_code,
        'Product Description': product['Product Description'],
        'Quantity': quantity,
        'Unit': unit,
        'Supplier Batch No': supplier_batch,
        'Sell By Date': sell_by_date,
        'Delivery Date': delivery_date,  # Added to maintain consistency
        'Received By': current_user['username']  # Added to maintain consistency
    }
    
    add_received_product(product_dict, auth_system)
    
    return {
        'Product Code': product_code,
        'Supplier Product Code': product['Supplier Product Code'],
        'Product Description': product['Product Description'],
        'Supplier': product['Supplier Name'],
        'Batch/Lot': batch_lot,
        'Supplier Batch No': supplier_batch,
        'Sell By Date': sell_by_date,
        'Department': product['Department'].strip(),
        'Sub-Department': SUB_DEPT_MAPPING.get(str(product['Sub-Department']), ('Unknown', 'Unknown'))[1].strip(),
        'Quantity': quantity,
        'Unit': unit,
        'Delivery Date': delivery_date,
        'Status': 'Delivered',
        'Processing Date': '',
        'Current Location': 'Receiving',
        'Handling History': f'Received at {delivery_date} by {current_user["username"]}',
        'Quality Checks': 'Initial check: Passed',
        'Temperature Log': [],
        'Received By': current_user["username"],
        'Processed By': '',
        'Delivery Approved By': '',
        'Delivery Approval Date': ''
    }

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
    product['Status'] = 'Processed'
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
    
    return product

# Barcode generation
def generate_barcode(data):
    code128 = barcode.get_barcode_class('code128')
    rv = io.BytesIO()
    code128(data, writer=ImageWriter()).write(rv)
    image = Image.open(rv)
    image.thumbnail((300, 300))
    return image

def generate_product_barcode(product_code, batch_no, sell_by_date):
    """Generate a barcode for a product using Code128 format."""
    try:
        # Create a unique identifier combining product info
        barcode_data = f"{product_code}|{batch_no}|{sell_by_date}"
        
        # Create barcodes directory if it doesn't exist
        barcode_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'barcodes')
        os.makedirs(barcode_dir, exist_ok=True)
        
        # Generate the barcode
        code128 = Code128(barcode_data, writer=ImageWriter())
        
        # Save barcode to file
        barcode_path = os.path.join(barcode_dir, f"{product_code}_{batch_no}.png")
        code128.save(barcode_path)
        
        return {
            'barcode_data': barcode_data,
            'barcode_path': barcode_path
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

        # Store barcode data in handling_history
        handling_history = f"Barcode Generated: {barcode_info['barcode_data']}\nBarcode Path: {barcode_info['barcode_path']}"

        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO received_products (
                product_code, description, quantity, unit, 
                supplier_batch, sell_by_date, received_date,
                received_by, status, department, handling_history
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            values['-PRODUCT_CODE-'],
            values['-DESCRIPTION-'],
            values['-QUANTITY-'],
            values['-UNIT-'],
            values['-SUPPLIER_BATCH-'],
            values['-SELL_BY_DATE-'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            current_user['username'],
            'active',
            current_user['department'],
            handling_history
        ))
        
        conn.commit()
        conn.close()
        return True, "Product added successfully with barcode"
        
    except sqlite3.Error as e:
        return False, f"Database error: {str(e)}"
    except Exception as e:
        return False, f"Error adding product: {str(e)}"

def show_product_details(product, auth_system):
    """Display detailed product information including barcode."""
    user_info = auth_system.get_current_user_info()
    manager_info = f"Viewed by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Viewed by: N/A"
    
    # Extract barcode information from handling_history
    barcode_path = None
    barcode_data = None
    if 'Handling History' in product:
        history_lines = product['Handling History'].split('\n')
        for line in history_lines:
            if line.startswith('Barcode Generated:'):
                barcode_data = line.replace('Barcode Generated:', '').strip()
            elif line.startswith('Barcode Path:'):
                barcode_path = line.replace('Barcode Path:', '').strip()
    
    layout = [
        [sg.Text('Product Details', font=FONT_HEADER)],
        [sg.Text(manager_info, font=FONT_SMALL)],
        [sg.Text(f"Product Code: {product['Product Code']}")],
        [sg.Text(f"Product Description: {product['Product Description']}")],
        [sg.Text(f"Quantity: {product['Quantity']} {product['Unit']}")],
        [sg.Text(f"Supplier Batch: {product.get('Supplier Batch No', 'N/A')}")],
        [sg.Text(f"Sell by Date: {product.get('Sell By Date', 'N/A')}")],
        [sg.Text(f"Received Date: {product.get('Received Date', 'N/A')}")],
        [sg.Text(f"Received By: {product.get('Received By', 'N/A')}")],
        [sg.Text(f"Status: {product.get('Status', 'N/A')}")],
    ]
    
    if barcode_data:
        layout.append([sg.Text(f"Barcode Data: {barcode_data}")])
    
    if barcode_path and os.path.exists(barcode_path):
        layout.append([sg.Image(barcode_path)])
    
    layout.extend([
        [sg.Text('Handling History:')],
        [sg.Multiline(product.get('Handling History', 'No handling history available'), size=(60, 5), disabled=True)],
        [sg.Text('Temperature Log:')],
        [sg.Multiline('\n'.join(product.get('Temperature Log', ['No temperature readings available'])), size=(60, 3), disabled=True)],
        [sg.Button('Close')]
    ])
    
    details_window = sg.Window('Product Details', layout, modal=True)
    
    while True:
        event, _ = details_window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
    
    details_window.close()

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
                 sg.Tab('Database Management', create_database_management_tab(), visible=auth_system.is_manager())]
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
    
    department_frames = []
    for dept in departments:
        frame_layout = [
            [sg.Table(values=[],
                      headings=['Product Code', 'Description', 'Quantity', 'Unit', 'Status'],
                      display_row_numbers=False,
                      auto_size_columns=True,
                      num_rows=5,
                      key=f'-{dept.upper()}_TABLE-',
                      enable_events=True)]
        ]
        department_frames.append(sg.Frame(f'{dept} Window', frame_layout, key=f'-{dept.upper()}_FRAME-'))

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
             sg.CalendarButton('Select Date', target='-SELL_BY_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['secondary']))],
            [sg.Button('Receive Product', size=(15, 1), button_color=(COLORS['text'], COLORS['primary']))],
        ], relief=sg.RELIEF_SUNKEN, expand_x=True, expand_y=True)],
        department_frames
    ]

def create_receiving_tab():
    layout = [
        [sg.Text('Receiving Overview', font=FONT_HEADER)],
        [sg.Column([
            [sg.Text('Active Products', font=FONT_SUBHEADER)],
            [sg.Table(values=[],
                     headings=['Product Code', 'Description', 'Quantity', 'Unit', 
                              'Supplier Batch', 'Sell By Date', 'Received Date', 'Received By'],
                     auto_size_columns=True,
                     display_row_numbers=False,
                     justification='left',
                     num_rows=15,
                     key='-RECEIVING_TABLE-',
                     enable_events=True)],
            [sg.Button('View Details', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Process Selected', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Generate Barcode', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Refresh', button_color=(COLORS['text'], COLORS['secondary']))]
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
            [sg.Button('View Processed Details', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('View History', button_color=(COLORS['text'], COLORS['primary']))]
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

    if event == 'Receive Product':
        product_code = values['-PRODUCT-']
        quantity = values['-QUANTITY-']
        unit = values['-UNIT-']
        supplier_batch = values['-SUPPLIER_BATCH-']
        sell_by_date = values['-SELL_BY_DATE-']
        

        if product_code and quantity and supplier_batch and sell_by_date:
            product = deliver_product(df, product_code, quantity, unit, supplier_batch, sell_by_date, auth_system)
            temp_log = record_temperature_popup()
            if temp_log:
                product['Temperature Log'].append(temp_log)
            
            barcode_info = generate_product_barcode(product_code, supplier_batch, sell_by_date)
            if barcode_info:
                product['barcode_data'] = barcode_info['barcode_data']
                product['barcode_path'] = barcode_info['barcode_path']
            
            inventory.append(product)
            update_inventory_table(window, inventory)
            update_department_tables(window, inventory)
            sg.popup('Product received successfully', font=FONT_NORMAL)
        else:
            sg.popup_error('Please fill in all required fields', font=FONT_NORMAL)

# Add a new function to update department-specific tables
def update_department_tables(window, inventory):
    departments = ['HMR', 'Butchery', 'Bakery']
    for dept in departments:
        dept_inventory = [item for item in inventory if item['Department'].lower() == dept.lower()]
        window[f'-{dept.upper()}_TABLE-'].update([
            [item['Product Code'], item['Product Description'], item['Quantity'], item['Unit'], item['Status']]
            for item in dept_inventory
        ])

def handle_receiving_events(event, values, window, inventory, auth_system):
    if event == '-RECEIVING_TABLE-':
        return
    
    if event == 'View Details':
        selected_rows = values['-RECEIVING_TABLE-']
        if not selected_rows:
            sg.popup('Please select a product to view details', font=FONT_NORMAL)
            return
        # Use the stored active_items to get the correct product
        selected_product = window.active_items[selected_rows[0]]
        show_product_details(selected_product, auth_system)
    
    elif event == 'View Processed Details':
        selected_rows = values['-PROCESSED_TABLE-']
        if not selected_rows:
            sg.popup('Please select a processed product to view details', font=FONT_NORMAL)
            return
        # Use the stored processed_items to get the correct product
        selected_product = window.processed_items[selected_rows[0]]
        show_product_details(selected_product, auth_system)
    
    elif event == 'View History':
        selected_rows = values['-PROCESSED_TABLE-']
        if not selected_rows:
            sg.popup('Please select a product to view history', font=FONT_NORMAL)
            return
        # Use the stored processed_items to get the correct product
        selected_product = window.processed_items[selected_rows[0]]
        layout = [
            [sg.Text('Product History', font=FONT_HEADER)],
            [sg.Text(f"Product: {selected_product['Product Description']}")],
            [sg.Text('Handling History:')],
            [sg.Multiline(selected_product.get('Handling History', 'No handling history available'), size=(60, 10), disabled=True)],
            [sg.Text('Temperature Log:')],
            [sg.Multiline('\n'.join(selected_product.get('Temperature Log', ['No temperature log available'])), size=(60, 5), disabled=True)],
            [sg.Button('Close')]
        ]
        history_window = sg.Window('Product History', layout, modal=True)
        while True:
            hist_event, _ = history_window.read()
            if hist_event in (sg.WIN_CLOSED, 'Close'):
                break
        history_window.close()
    
    elif event == 'Process Selected':
        selected_rows = values['-RECEIVING_TABLE-']
        if not selected_rows:
            sg.popup('Please select products to process', font=FONT_NORMAL)
            return
        user_info = auth_system.get_current_user_info()
        if not user_info or user_info['role'] != 'Manager':
            sg.popup_error('You are not authorized to process products. Only Managers can process products.', font=FONT_NORMAL)
        else:
            # Use the stored active_items to get the correct products
            selected_products = [window.active_items[row] for row in selected_rows]
            process_selected_products(auth_system, inventory, selected_products, window)
            # Update both tables after processing
            update_inventory_table(window, inventory)
            update_processed_table(window, inventory)
    
    elif event == 'Generate Barcode':
        selected_rows = values['-RECEIVING_TABLE-']
        if not selected_rows:
            sg.popup('Please select a product to generate barcode', font=FONT_NORMAL)
            return
        # Use the stored active_items to get the correct product
        selected_product = window.active_items[selected_rows[0]]
        generate_and_show_barcode(selected_product)
    
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
            if refresh_display(window, inventory, auth_system):
                sg.popup('Success', 'Data refreshed successfully.', font=FONT_NORMAL)
            else:
                sg.popup_error('Error', 'Failed to refresh data. Please try again.')

def department_login_window(auth_system, inventory, selected_rows, main_window):
    layout = [
        [sg.Text('Department Manager Login', font=FONT_SUBHEADER)],
        [sg.Text('Username:', size=(15, 1)), sg.Input(key='-USERNAME-')],
        [sg.Text('Password:', size=(15, 1)), sg.Input(key='-PASSWORD-', password_char='*')],
        [sg.Button('Login', size=(10, 1), button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Cancel', size=(10, 1), button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    window = sg.Window('Department Manager Login', layout)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        if event == 'Login':
            username = values['-USERNAME-']
            password = values['-PASSWORD-']
            if auth_system.login(username, password):
                window.close()
                process_selected_products(auth_system, inventory, selected_rows, main_window)
                auth_system.logout()
                return
            else:
                sg.popup_error('Login failed. Please try again.')

    window.close()

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
            if 'Temperature Log' not in product:
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
            handling_history = ?
        WHERE product_code = ? AND supplier_batch = ?
    ''', (
        product['Status'],
        handling_history,
        product['Product Code'],
        product.get('Supplier Batch No', '')
    ))
    
    # Update processed_by and processing_date in a separate query if they exist
    if product.get('Processed By') and product.get('Processing Date'):
        cursor.execute('''
            UPDATE received_products
            SET processed_by = ?,
                processing_date = ?
            WHERE product_code = ? AND supplier_batch = ?
        ''', (
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
    recipes = {}
    try:
        df = pd.read_csv('DEPARTMENTS - RECIPES - ALL DEPT..csv')
        
        # Initialize variables for tracking current recipe
        current_dept = None
        current_recipe = None
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
                current_ingredients = []
            
            # Add ingredient to current recipe
            if pd.notna(row['Ingredient Prod Code']):
                ingredient = [
                    str(row['Ingredient Prod Code']),
                    str(row['Ingredient Description']),
                    str(row['Recipe']) if pd.notna(row['Recipe']) else '0',
                    str(row['Pack Deliver']) if pd.notna(row['Pack Deliver']) else 'P/KG'
                ]
                current_recipe['ingredients'].append(ingredient)
        
        # Add the last recipe
        if current_recipe is not None:
            if current_dept not in recipes:
                recipes[current_dept] = []
            recipes[current_dept].append(current_recipe)
            
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
    if event == '-GENERATE_REPORT-':
        try:
            start_date = datetime.strptime(values['-START_DATE-'], '%Y-%m-%d')
            end_date = datetime.strptime(values['-END_DATE-'], '%Y-%m-%d')
            report_type = values['-REPORT_TYPE-']
            
            # Get raw report data
            report_data = generate_report(inventory, report_type, start_date, end_date, auth_system)
            
            # Format report for display
            formatted_report = format_report_for_display(report_data, report_type, auth_system)
            window['-REPORT_PREVIEW-'].update(formatted_report)
            
            # Store raw data for saving
            window.user_data = {
                'current_report': {
                    'data': report_data,
                    'type': report_type,
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            
        except ValueError as e:
            sg.popup_error(f'Error generating report: {str(e)}', title='Report Generation Error')
            
    elif event == '-SAVE_PDF-':
        try:
            if not hasattr(window, 'user_data') or 'current_report' not in window.user_data:
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
                sg.popup('Report saved successfully!', title='Success')
                
        except Exception as e:
            sg.popup_error(f'Error saving PDF: {str(e)}', title='PDF Export Error')
            
    elif event == '-SAVE_CSV-':
        try:
            if not hasattr(window, 'user_data') or 'current_report' not in window.user_data:
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
                sg.popup('Report saved successfully!', title='Success')
                
        except Exception as e:
            sg.popup_error(f'Error saving CSV: {str(e)}', title='CSV Export Error')

def generate_report(inventory, report_type, start_date, end_date, auth_system):
    try:
        if not auth_system or not auth_system.get_current_user_info():
            raise ValueError("User not authenticated")
            
        if report_type == 'Inventory Summary':
            return generate_inventory_summary(inventory, start_date, end_date, auth_system)
        elif report_type == 'Traceability Report':
            return generate_traceability_report(inventory, start_date, end_date, auth_system)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
    except Exception as e:
        raise Exception(f"Error generating report: {str(e)}")

def update_product_fields(window, product):
    window['-PRODUCT-'].update(product['Product Code'])
    window['-SUPPLIER_PRODUCT-'].update(product['Supplier Product Code'])
    window['-DEPARTMENT-'].update(product['Department'])

def update_inventory_table(window, inventory):
    """Update the inventory table with active (unprocessed) items."""
    # Filter active (unprocessed) items and store them as a class attribute
    window.active_items = [item for item in inventory if item['Status'] != 'Processed']
    
    # Format active items for display
    active_data = [[
        item['Product Code'],
        item['Product Description'],
        item['Quantity'],
        item['Unit'],
        item['Supplier Batch No'],
        item['Sell By Date'],
        item.get('Received Date', ''),  # Changed from 'Delivery Date' to 'Received Date'
        item.get('Received By', '')
    ] for item in window.active_items]
    
    # Get currently displayed data
    current_data = window['-RECEIVING_TABLE-'].get()
    
    # Only update if there are actual changes in the data
    if current_data != active_data:
        window['-RECEIVING_TABLE-'].update(active_data)

def update_processed_table(window, inventory):
    """Update the processed items table."""
    # Store processed items as a class attribute
    window.processed_items = [item for item in inventory if item['Status'] == 'Processed']
    
    processed_data = [[
        item['Product Code'],
        item['Product Description'],
        item['Quantity'],
        item['Unit'],
        item.get('Processing Date', 'N/A'),
        item.get('Processed By', 'N/A'),
        item.get('Temperature Log', [])[-1] if item.get('Temperature Log') else 'N/A',
        item['Status']
    ] for item in window.processed_items]
    
    # Get currently displayed data
    current_data = window['-PROCESSED_TABLE-'].get()
    
    # Only update if the data is different
    if current_data != processed_data:
        window['-PROCESSED_TABLE-'].update(processed_data)

def refresh_display(window, inventory, auth_system):
    """
    Safely refresh the display without modifying processed product data.
    Only updates the visual representation of data that hasn't been processed.
    
    Args:
        window: The PySimpleGUI window object
        inventory: The current inventory data
        auth_system: The authentication system for access control
    """
    # Get current user's department
    current_user = auth_system.get_current_user_info()
    if current_user is None:
        return False
        
    try:
        # Get fresh inventory data for unprocessed items from the department
        department_inventory = get_department_inventory(current_user['department'])
        
        # Separate processed and unprocessed items in current inventory
        processed_items = [item for item in inventory if item['Status'] == 'Processed']
        
        # Clear and update inventory with processed items and fresh unprocessed items
        inventory.clear()
        inventory.extend(processed_items)  # Keep processed items unchanged
        inventory.extend(department_inventory)  # Add fresh unprocessed items
        
        # Update the display tables
        update_processed_table(window, inventory)
        update_inventory_table(window, inventory)
        
        return True
        
    except Exception as e:
        sg.popup_error('Database Error', f'Error refreshing data: {str(e)}')
        return False
    
    return True

def show_login_window(auth_system):
    layout = [
        [sg.Text('Username:', size=(15, 1)), sg.Input(key='-USERNAME-')],
        [sg.Text('Password:', size=(15, 1)), sg.Input(key='-PASSWORD-', password_char='*')],
        [sg.Button('Login', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Exit', button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    window = sg.Window('Login', layout)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            window.close()
            return False
        if event == 'Login':
            if auth_system.login(values['-USERNAME-'], values['-PASSWORD-']):
                sg.popup('Login successful!')
                window.close()
                return True
            else:
                sg.popup_error('Login failed. Please try again.')
    
        window.close()
        return False

def record_temperature_popup():
    locations = [
        'Receiving', 'Hot Foods', 'Butchery', 'Bakery', 'Fruit & Veg',
        'Admin', 'Coffee shop', 'Floor', 'Location 9', 'Location 10', 'Location 11'
    ]
    
    layout = [
        [sg.Text('Record Temperature', font=FONT_NORMAL)],
        [sg.Text('Temperature:', font=FONT_NORMAL), sg.Input(key='-TEMP-', font=FONT_NORMAL)],
        [sg.Text('Location:', font=FONT_NORMAL), 
         sg.Combo(locations, default_value=locations[0], key='-LOCATION-', font=FONT_NORMAL, readonly=True)],
        [sg.Button('Submit', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Cancel', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    
    window = sg.Window('Record Temperature', layout)
    
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            window.close()
            return None
        if event == 'Submit':
            try:
                temp = float(values['-TEMP-'])
                location = values['-LOCATION-']
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                window.close()
                return f"{timestamp}: {temp}°C at {location}"
            except ValueError:
                sg.popup_error('Please enter a valid temperature', font=FONT_NORMAL)
    
        window.close()

def generate_and_show_barcode(item):
    # Create a combined identifier with timestamp for better traceability
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    combined_batch = f"{item['Product Code']}-{item['Supplier Batch No']}-{timestamp}"
    barcode_image = generate_barcode(combined_batch)
    
    bio = io.BytesIO()
    barcode_image.save(bio, format="PNG")
    barcode_data = bio.getvalue()
    
    # Format timestamp for display
    display_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    layout = [
        [sg.Text(item['Product Description'], font=FONT_NORMAL)],
        [sg.Text(f"Product Code: {item['Product Code']}")],
        [sg.Text(f"Batch: {item['Supplier Batch No']}")],
        [sg.Text(f"Generated: {display_timestamp}", font=FONT_NORMAL)],
        [sg.Text(f"Tracking ID: {combined_batch}", font=FONT_NORMAL)],
        [sg.Image(data=barcode_data, key='-IMAGE-')],
        [sg.Button('Save Barcode', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Close', font=FONT_NORMAL, button_color=(COLORS['text'], COLORS['secondary']))]
    ]
    
    window = sg.Window('Barcode', layout)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
        elif event == 'Save Barcode':
            save_barcode(barcode_image, item)
            sg.popup('Barcode saved successfully!', font=FONT_NORMAL)
    window.close()

def save_barcode(image, item):
    filename = sg.popup_get_file('Save Barcode as PNG', save_as=True, file_types=(("PNG Files", "*.png"),))
    if filename:
        if not filename.lower().endswith('.png'):
            filename += '.png'
        image.save(filename)
        sg.popup(f"Barcode saved as {filename}")

def save_as_pdf(report, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=10)
    
    # Split content into lines and write to PDF
    lines = report.split('\n')
    for line in lines:
        # Remove any special characters used for formatting in the preview
        clean_line = line.replace('║', '|').replace('╔', '+').replace('╚', '+').replace('─', '-')
        pdf.cell(0, 5, txt=clean_line, ln=True)
    
    pdf.output(filename)

def save_as_csv(report, filename):
    with open(filename, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=report[0].keys())
        writer.writeheader()
        writer.writerows(report)

def initialize_database():
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    # Create received products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS received_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT,
            description TEXT,
            quantity REAL,
            unit TEXT,
            department TEXT,
            received_by TEXT,
            received_date DATETIME,
            supplier_batch TEXT,
            sell_by_date TEXT,
            status TEXT DEFAULT 'active',
            handling_history TEXT DEFAULT '',
            temperature_log TEXT DEFAULT '',
            processed_by TEXT,
            processing_date TEXT,
            barcode_data TEXT,
            barcode_image TEXT
        )
    ''')
    
    # Check if columns exist and add them if they don't
    cursor.execute("PRAGMA table_info(received_products)")
    columns = [info[1] for info in cursor.fetchall()]
    
    required_columns = {
        'handling_history': 'TEXT DEFAULT ""',
        'temperature_log': 'TEXT DEFAULT ""',
        'processed_by': 'TEXT',
        'processing_date': 'TEXT',
        'barcode_data': 'TEXT',
        'barcode_image': 'TEXT'
    }
    
    for col_name, col_type in required_columns.items():
        if col_name not in columns:
            cursor.execute(f'ALTER TABLE received_products ADD COLUMN {col_name} {col_type}')
    
    conn.commit()
    conn.close()

def add_received_product(product, auth_system):
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    current_user = auth_system.get_current_user_info()
    
    cursor.execute('''
        INSERT INTO received_products 
        (product_code, description, quantity, unit, department, received_by, 
         received_date, supplier_batch, sell_by_date, barcode_data, barcode_image)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        product['Product Code'],
        product['Product Description'],  # Changed from Description
        product['Quantity'],
        product['Unit'],
        current_user['department'],
        current_user['username'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        product.get('Supplier Batch No', ''),  # Changed from Supplier Batch
        product.get('Sell By Date', ''),
        product.get('barcode_data', ''),
        product.get('barcode_image', '')
    ))
    
    conn.commit()
    conn.close()

def get_department_inventory(department):
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT product_code, description, quantity, unit, supplier_batch, 
               sell_by_date, received_date, received_by, status, department,
               COALESCE(handling_history, '') as handling_history,
               COALESCE(temperature_log, '') as temperature_log
        FROM received_products
        WHERE department = ? AND status = 'active'
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
        item['Received Date'] = item.pop('received_date')
        item['Received By'] = item.pop('received_by')
        item['Status'] = item.pop('status')
        item['Department'] = item.pop('department')
        item['Handling History'] = item.pop('handling_history', '')
        item['Temperature Log'] = item.pop('temperature_log', '').split('\n') if item.get('temperature_log') else []
        
        # Extract barcode information from handling history
        if item['Handling History']:
            history_lines = item['Handling History'].split('\n')
            for line in history_lines:
                if line.startswith('Barcode Generated:'):
                    item['barcode_data'] = line.replace('Barcode Generated:', '').strip()
                elif line.startswith('Barcode Path:'):
                    item['barcode_path'] = line.replace('Barcode Path:', '').strip()
        
        inventory.append(item)
    
    conn.close()
    return inventory

def create_database_management_tab():
    today = datetime.now()
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
                enable_events=True
            )]
        ])],
        [sg.Frame('Export Options', [
            [sg.Button('Export to CSV', key='-DB-EXPORT-CSV-', button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Button('Export to PDF', key='-DB-EXPORT-PDF-', button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Button('View Details', key='-DB-VIEW-DETAILS-', button_color=(COLORS['text'], COLORS['primary']))]
        ])]
    ]
    return layout

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
        if not window['-DB-TABLE-'].get():
            sg.popup_error('No Data', 'Please perform a search first.')
            return
        filename = sg.popup_get_file('Save CSV As', save_as=True, file_types=(("CSV Files", "*.csv"),))
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
        if not window['-DB-TABLE-'].get():
            sg.popup_error('No Data', 'Please perform a search first.')
            return
        filename = sg.popup_get_file('Save PDF As', save_as=True, file_types=(("PDF Files", "*.pdf"),))
        if filename:
            try:
                pdf = FPDF()
                pdf.add_page()
                
                # Set font
                pdf.set_font("Arial", "B", 16)
                
                # Title
                pdf.cell(0, 10, f"SPATRAC Database Search Results", ln=True, align='C')
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
                sg.popup('Success', f"Report saved as {filename}")
                
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

def show_database_product_details(product, auth_system):
    # Format dates for display
    received_date = product.get('received_date', 'N/A')
    processing_date = product.get('processing_date', 'N/A')
    
    # Format handling history for display
    handling_history = product.get('handling_history', [])
    if isinstance(handling_history, str):
        handling_history = handling_history.split('\n')
    history_text = '\n'.join(handling_history) if handling_history else 'No handling history'
    
    layout = [
        [sg.Text('Product Details', font=FONT_HEADER)],
        [sg.Text(f"Product Code: {product.get('product_code', 'N/A')}")],
        [sg.Text(f"Description: {product.get('description', 'N/A')}")],
        [sg.Text(f"Current Department: {product.get('department', 'N/A')}")],
        [sg.Text(f"Quantity: {product.get('quantity', 'N/A')} {product.get('unit', '')}")],
        [sg.Text(f"Status: {product.get('status', 'N/A')}")],
        [sg.Text(f"Supplier Batch: {product.get('supplier_batch', 'N/A')}")],
        [sg.Text(f"Received Date: {received_date}")],
        [sg.Text(f"Received By: {product.get('received_by', 'N/A')}")],
        [sg.Text(f"Processing Date: {processing_date}")],
        [sg.Text(f"Processed By: {product.get('processed_by', 'N/A')}")],
        [sg.Text('Handling History:', font=FONT_NORMAL)],
        [sg.Multiline(history_text, size=(60, 5), disabled=True)],
        [sg.Button('Close')]
    ]
    
    window = sg.Window('Product Details', layout, modal=True)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
    window.close()

def load_final_products(department):
    """Load final products for a specific department."""
    try:
        with open(f'data/{department.lower()}_final_products.csv', 'r') as file:
            reader = csv.DictReader(file)
            return list(reader)
    except FileNotFoundError:
        return []    

def create_reports_tab():
    today = datetime.now()
    layout = [
        [sg.Text('Reports', font=FONT_HEADER, justification='center', expand_x=True)],
        [sg.Frame('Report Options', [
            [sg.Text('Report Type:'),
             sg.Combo(['Inventory Summary', 'Traceability Report'], 
                     default_value='Inventory Summary', key='-REPORT_TYPE-', size=(20,1))],
            [sg.Text('Date Range:')],
            [sg.Text('From:'), 
             sg.Input(key='-START_DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d')),
             sg.CalendarButton('Choose', target='-START_DATE-', format='%Y-%m-%d', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Text('To:'), 
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
    return layout

def save_report_as_pdf(filename, report_data, report_type, start_date, end_date, auth_system):
    """Save the report as a PDF file."""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"SPATRAC - {report_type}", ln=True, align='C')
        pdf.ln(5)
        
        # User Info
        user_info = auth_system.get_current_user_info()
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"Department: {user_info['department']}", ln=True)
        pdf.cell(0, 8, f"Generated by: {user_info['username']} ({user_info['role']})", ln=True)
        pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.cell(0, 8, f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", ln=True)
        pdf.ln(10)
        
        if report_type == 'Inventory Summary':
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
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 10, "Report End", ln=True, align='C')
        pdf.cell(0, 10, "Generated by SPATRAC System", ln=True, align='C')
        pdf.cell(0, 10, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ln=True, align='C')
        
        pdf.output(filename)
        return True
    except Exception as e:
        raise Exception(f"Error creating PDF: {str(e)}")

def save_report_as_csv(filename, report_data, report_type, start_date, end_date, auth_system):
    try:
        user_info = auth_system.get_current_user_info()
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header rows
            writer.writerow(['SPATRAC - ' + report_type])
            writer.writerow(['Department: ' + user_info['department']])
            writer.writerow(['Generated by: ' + user_info['username'] + ' (' + user_info['role'] + ')'])
            writer.writerow(['Date: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['Period: ' + start_date.strftime('%Y-%m-%d') + ' to ' + end_date.strftime('%Y-%m-%d')])
            writer.writerow([])  # Empty row for spacing
            
            if report_type == 'Inventory Summary':
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
                    
            elif report_type == 'Traceability Report':
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
            
            # Write footer
            writer.writerow([])  # Empty row for spacing
            writer.writerow(['Report End'])
            writer.writerow(['Generated by SPATRAC System'])
            writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            
        return True
    except Exception as e:
        raise Exception(f"Error saving CSV: {str(e)}")

def format_report_for_display(report_data, report_type, auth_system):
    """Format the report data for display in the GUI."""
    user_info = auth_system.get_current_user_info()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    header = f"""
SPATRAC {report_type}
─────────────────────────────────────────────────────────────────
Generated by: {user_info['username']}
Department: {user_info['department']}
Date: {current_time}
─────────────────────────────────────────────────────────────────

"""
    
    if report_type == 'Inventory Summary':
        body = ""
        for item in report_data:
            body += f"""
Product Code: {item.get('Product Code', 'N/A')}
Name: {item.get('Name', 'N/A')}
Quantity: {item.get('Quantity', 'N/A')}
Status: {item.get('Status', 'N/A')}
─────────────────────────────────────────────────────────────────"""
    
    elif report_type == 'Traceability Report':
        body = ""
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
    
    footer = f"""

Report End
Generated by SPATRAC System
{current_time}
"""
    
    return header + body + footer

def show_product_details(product, auth_system):
    """Display detailed product information including barcode."""
    user_info = auth_system.get_current_user_info()
    manager_info = f"Viewed by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Viewed by: N/A"
    
    # Create temporary file for barcode image if available
    barcode_image_path = None
    if product.get('barcode_image'):
        try:
            import tempfile
            temp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            temp.write(base64.b64decode(product['barcode_image']))
            temp.close()
            barcode_image_path = temp.name
        except Exception as e:
            print(f"Error creating barcode image: {str(e)}")
    
    layout = [
        [sg.Text('Product Details', font=FONT_HEADER)],
        [sg.Text(manager_info, font=FONT_SMALL)],
        [sg.Text(f"Product Code: {product['Product Code']}")],
        [sg.Text(f"Product Description: {product['Product Description']}")],
        [sg.Text(f"Quantity: {product['Quantity']} {product['Unit']}")],
        [sg.Text(f"Supplier Batch: {product.get('Supplier Batch No', 'N/A')}")],
        [sg.Text(f"Sell by Date: {product.get('Sell By Date', 'N/A')}")],
        [sg.Text(f"Received Date: {product.get('Received Date', 'N/A')}")],
        [sg.Text(f"Received By: {product.get('Received By', 'N/A')}")],
        [sg.Text(f"Status: {product.get('Status', 'N/A')}")],
        [sg.Text(f"Barcode Data: {product.get('barcode_data', 'N/A')}")],
    ]
    
    if barcode_image_path:
        layout.append([sg.Image(barcode_image_path)])
    
    layout.extend([
        [sg.Text('Handling History:')],
        [sg.Multiline(product.get('Handling History', 'No handling history available'), size=(60, 5), disabled=True)],
        [sg.Text('Temperature Log:')],
        [sg.Multiline('\n'.join(product.get('Temperature Log', ['No temperature readings available'])), size=(60, 3), disabled=True)],
        [sg.Button('Close')]
    ])
    
    details_window = sg.Window('Product Details', layout, modal=True)
    
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

if __name__ == "__main__":
    initialize_database()  # Initialize/update database schema
    file_paths = ['Butchery reports Big G.csv', 'Bakery Big G.csv', 'HMR Big G.csv']
    df = load_data(file_paths)
    create_gui(df)