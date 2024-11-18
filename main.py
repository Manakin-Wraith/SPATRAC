import pandas as pd
import PySimpleGUI as sg
import csv
from fpdf import FPDF
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import io
from PIL import Image
from auth_system import AuthSystem
import json
import sqlite3

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
    current_user = auth_system.get_current_user()
    product_dict = {
        'Product Code': product_code,
        'Description': product['Product Description'],
        'Quantity': quantity,
        'Unit': unit,
        'Supplier Batch': supplier_batch,
        'Sell By Date': sell_by_date
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
        'Delivery Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Status': 'Delivered',
        'Processing Date': '',
        'Current Location': 'Receiving',
        'Handling History': f'Received at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} by {current_user}',
        'Quality Checks': 'Initial check: Passed',
        'Temperature Log': [],
        'Received By': current_user,
        'Processed By': '',
        'Delivery Approved By': '',
        'Delivery Approval Date': ''
    }

def approve_delivery(product, auth_system):
    current_user = auth_system.get_current_user()
    approval_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product['Status'] = 'Delivery Approved'
    product['Delivery Approved By'] = current_user
    product['Delivery Approval Date'] = approval_date
    product['Handling History'] += f"\nDelivery approved at {approval_date} by {current_user}"
    return product

def process_product(product, auth_system):
    current_user = auth_system.get_current_user()
    processing_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product['Status'] = 'Processed'
    product['Processing Date'] = processing_date
    product['Current Location'] = f"{product['Department']} - {product['Sub-Department']}"
    product['Handling History'] += f"\nProcessed at {processing_date} by {current_user}"
    product['Quality Checks'] += f"\nPre-processing check: Passed"
    product['Processed By'] = current_user
    return product

# Barcode generation
def generate_barcode(data):
    code128 = barcode.get_barcode_class('code128')
    rv = io.BytesIO()
    code128(data, writer=ImageWriter()).write(rv)
    image = Image.open(rv)
    image.thumbnail((300, 300))
    return image

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
                 sg.Tab('Receiving', create_inventory_tab()),
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
            handle_inventory_events(event, values, window, inventory, auth_system)
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

def create_inventory_tab():
    layout = [
        [sg.Text('Inventory Overview', font=FONT_HEADER)],
        [sg.Table(values=[],
                 headings=['Product Code', 'Description', 'Quantity', 'Unit', 
                          'Supplier Batch', 'Sell By Date', 'Received Date', 'Received By'],
                 auto_size_columns=True,
                 display_row_numbers=False,
                 justification='left',
                 num_rows=20,
                 key='-INVENTORY_TABLE-',
                 enable_events=True)],
        [sg.Button('Refresh', button_color=(COLORS['text'], COLORS['primary']))]
    ]
    return layout

def create_reports_tab():
    today = datetime.now()
    return [
        [sg.Frame('Generate Reports', [
            [sg.Text('Report Type:'),
             sg.Combo(['Inventory Summary', 'Traceability', 'Temperature Log'],
                     default_value='Inventory Summary',
                     key='-REPORT_TYPE-', size=(20, 1))],
            [sg.Text('Date Range:')],
            [sg.Text('Start Date:'),
             sg.Input(key='-START_DATE-', size=(20, 1), default_text=today.strftime('%Y-%m-%d')),
             sg.CalendarButton('Select', target='-START_DATE-', format='%Y-%m-%d',
                             button_color=(COLORS['text'], COLORS['primary']))],
            [sg.Text('End Date:'),
             sg.Input(key='-END_DATE-', size=(20, 1), default_text=today.strftime('%Y-%m-%d')),
             sg.CalendarButton('Select', target='-END_DATE-', format='%Y-%m-%d',
                             button_color=(COLORS['text'], COLORS['primary']))],
            [sg.Button('Generate Report', key='-GENERATE_REPORT-', button_color=(COLORS['text'], COLORS['primary'])),
             sg.Button('Save as PDF', key='-SAVE_PDF-', button_color=(COLORS['text'], COLORS['secondary'])),
             sg.Button('Save as CSV', key='-SAVE_CSV-', button_color=(COLORS['text'], COLORS['secondary']))]
        ], relief=sg.RELIEF_SUNKEN, expand_x=True)],
        [sg.Frame('Report Preview', [
            [sg.Multiline(size=(80, 30), key='-REPORT_PREVIEW-', font=('Courier', 10),
                         background_color='white', text_color='black', expand_x=True, expand_y=True)]
        ], relief=sg.RELIEF_SUNKEN, expand_x=True, expand_y=True)]
    ]

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

def handle_inventory_events(event, values, window, inventory, auth_system):
    if event == 'Refresh':
        # Get current user's department
        current_user = auth_system.get_current_user_info()
        department_inventory = get_department_inventory(current_user['department'])
        
        # Convert to display format
        inventory_display = [[
            row[0],  # Product Code
            row[1],  # Description
            row[2],  # Quantity
            row[3],  # Unit
            row[4],  # Supplier Batch
            row[5],  # Sell By Date
            row[6],  # Received Date
            row[7]   # Received By
        ] for row in department_inventory]
        
        window['-INVENTORY_TABLE-'].update(inventory_display)

    if event == 'View Details':
        selected_rows = values['-INVENTORY_TABLE-']
        if selected_rows:
            selected_product = inventory[selected_rows[0]]
            show_product_details(selected_product, auth_system)
        else:
            sg.popup_error('Please select a product to view details', font=FONT_NORMAL)

    if event == 'Process Selected':
        selected_rows = values['-INVENTORY_TABLE-']
        if selected_rows:
            user_info = auth_system.get_current_user_info()
            if user_info is None:
                sg.popup_error('Error: No user is currently logged in.', font=FONT_NORMAL)
            elif user_info['role'] != 'Manager':
                sg.popup_error('You are not authorized to process products. Only Managers can process products.', font=FONT_NORMAL)
            else:
                process_selected_products(auth_system, inventory, selected_rows, window)
        else:
            sg.popup_error('Please select products to process', font=FONT_NORMAL)

    if event == 'Generate Barcode':
        selected_rows = values['-INVENTORY_TABLE-']
        if selected_rows:
            selected_product = inventory[selected_rows[0]]
            generate_and_show_barcode(selected_product)
        else:
            sg.popup_error('Please select a product to generate a barcode', font=FONT_NORMAL)


def department_login_window(auth_system, inventory, selected_rows, main_window):
    layout = [
        [sg.Text('Department Manager Login', font=FONT_SUBHEADER)],
        [sg.Text('Username:', size=(15, 1)), sg.Input(key='-USERNAME-')],
        [sg.Text('Password:', size=(15, 1)), sg.Input(key='-PASSWORD-', password_char='*')],
        [sg.Button('Login', button_color=(COLORS['text'], COLORS['primary'])),
         sg.Button('Cancel', button_color=(COLORS['text'], COLORS['secondary']))]
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

def process_selected_products(auth_system, inventory, selected_rows, window):
    user_info = auth_system.get_current_user_info()
    if user_info is None:
        sg.popup_error('Error: No user is currently logged in.', font=FONT_NORMAL)
        return

    if user_info['role'] != 'Manager':
        sg.popup_error('You are not authorized to process products. Only Managers can process products.', font=FONT_NORMAL)
        return

    processed_products = []
    for idx in selected_rows:
        product = inventory[idx]
        if product['Status'] != 'Processed' and auth_system.is_authorized(user_info['username'], product['Department']):
            processed_product = process_product(product, auth_system)
            processed_product['Processed By'] = f"{user_info['username']} ({user_info['role']})"
            inventory[idx] = processed_product
            processed_products.append([
                processed_product['Product Code'],
                processed_product['Product Description'],
                processed_product['Quantity'],
                processed_product['Unit']
            ])
    
    update_inventory_table(window, inventory)
    update_department_tables(window, inventory)
    
    if processed_products:
        department = user_info['department']
        final_products = load_final_products(department)
        dept_window = create_department_window(department, processed_products, final_products)
        handle_department_window(dept_window, processed_products, final_products)
    
        sg.popup('Selected products processed successfully', font=FONT_NORMAL)

    else:
        sg.popup_error('You are not authorized to process products', font=FONT_NORMAL)

def load_final_products(department):
    # This is a placeholder. In a real application, you would load this data from a database or file.
    final_products = {
        'HMR': [
            ['28820', 'FOOTLONG CHEESE GRILLER + CHIPS', '22585', 'SPAR SC CHS GRILLR F/LONG', '1'],
            ['28820', 'FOOTLONG CHEESE GRILLER + CHIPS', '26734', 'SOFT HOTDOG ROLLS', '1'],
            ['28820', 'FOOTLONG CHEESE GRILLER + CHIPS', '28442', 'GARLIC MAYO', '0.02'],
            ['28820', 'FOOTLONG CHEESE GRILLER + CHIPS', '26221', 'SPAR SC RUSTIC ST/H CHIPS', '0.06'],
        ],
        'BUTCHERY': [
            ['26665', 'BABALAS BRAAI WORS', '28557', 'CHICKEN MDM', '25'],
            ['26665', 'BABALAS BRAAI WORS', '28760', 'BEEF KIDNEY FAT', '25'],
            ['26665', 'BABALAS BRAAI WORS', '29030', 'SPAR WATER', '30'],
            ['26665', 'BABALAS BRAAI WORS', '30590', 'PARTY BRAAIWORS', '15'],
        ],
        'BAKERY': [
            ['26710', 'WHITE BREAD', '15736', 'W/CAPE MILL MIX WHT BRD', '47.5'],
            ['26710', 'WHITE BREAD', '28779', 'YEAST WET', '1'],
            ['26710', 'WHITE BREAD', '29030', 'SPAR WATER', '24.7'],
        ]
    }
    return final_products.get(department.upper(), [])

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

def handle_reports_events(event, values, window, inventory, auth_system):  # Added auth_system parameter
    try:
        if event == '-GENERATE_REPORT-':
            report_type = values['-REPORT_TYPE-']
            start_date = values['-START_DATE-']
            end_date = values['-END_DATE-']
            
            if not all([report_type, start_date, end_date]):
                sg.popup_error('Please select report type and date range', font=FONT_NORMAL)
                return
                
            try:
                # Validate dates
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                sg.popup_error('Invalid date format. Please use YYYY-MM-DD', font=FONT_NORMAL)
                return
                
            try:
                report = generate_report(inventory, report_type, start_date, end_date, auth_system)
                formatted_report = format_report_for_display(report, report_type, auth_system)
                window['-REPORT_PREVIEW-'].update(formatted_report)
            except Exception as e:
                sg.popup_error(f'Error generating report: {str(e)}', font=FONT_NORMAL)

        elif event == '-SAVE_PDF-':
            report = values['-REPORT_PREVIEW-']
            if not report:
                sg.popup_error('Please generate a report first', font=FONT_NORMAL)
                return
                
            filename = sg.popup_get_file('Save PDF as', save_as=True, file_types=(("PDF Files", "*.pdf"),))
            if filename:
                try:
                    save_as_pdf(report, filename)
                    sg.popup(f"Report saved as {filename}")
                except Exception as e:
                    sg.popup_error(f'Error saving PDF: {str(e)}', font=FONT_NORMAL)

        elif event == '-SAVE_CSV-':
            report = values['-REPORT_PREVIEW-']
            if not report:
                sg.popup_error('Please generate a report first', font=FONT_NORMAL)
                return
                
            filename = sg.popup_get_file('Save CSV as', save_as=True, file_types=(("CSV Files", "*.csv"),))
            if filename:
                try:
                    save_as_csv(report, filename)
                    sg.popup(f"Report saved as {filename}")
                except Exception as e:
                    sg.popup_error(f'Error saving CSV: {str(e)}', font=FONT_NORMAL)
                    
    except Exception as e:
        sg.popup_error(f'An unexpected error occurred: {str(e)}', font=FONT_NORMAL)

def format_report_for_display(report_data, report_type, auth_system):
    user_info = auth_system.get_current_user_info()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    header = f"""
╔══════════════════════════════════════════════════════════════════════════════
║ SPATRAC - {report_type}
║ Department: {user_info['department']}
║ Generated by: {user_info['username']} ({user_info['role']})
║ Date: {current_time}
╚══════════════════════════════════════════════════════════════════════════════

"""
    
    if report_type == 'Inventory Summary':
        # Group items by product code for summary
        summary = {}
        total_items = 0
        total_quantity = 0
        
        for item in report_data:
            code = item['Product Code']
            if code not in summary:
                summary[code] = {
                    'description': item['Description'],
                    'quantity': 0,
                    'unit': item['Unit']
                }
            summary[code]['quantity'] += float(item['Quantity'])
            total_items += 1
            total_quantity += float(item['Quantity'])
        
        body = f"""
Summary Statistics:
─────────────────────────────────────────────────────────────────
Total Unique Products: {len(summary)}
Total Items: {total_items}
Total Quantity: {total_quantity}

Detailed Inventory:
─────────────────────────────────────────────────────────────────
"""
        
        for code, data in summary.items():
            body += f"""
Product Code: {code}
Description: {data['description']}
Total Quantity: {data['quantity']} {data['unit']}
─────────────────────────────────────────────────────────────────"""
            
    elif report_type == 'Traceability':
        body = "Traceability Details:\n"
        body += "─────────────────────────────────────────────────────────────────\n\n"
        
        for item in report_data:
            body += f"""
Product Information:
• Code: {item['Product Code']}
• Description: {item['Description']}
• Batch: {item['Supplier Batch']}
• Sell By: {item['Sell By Date']}

Tracking Information:
• Received: {item['Received Date']}
• Received By: {item['Received By']}
─────────────────────────────────────────────────────────────────"""
            
    elif report_type == 'Temperature Log':
        body = "Temperature Log Entries:\n"
        body += "─────────────────────────────────────────────────────────────────\n\n"
        
        for log in report_data:
            body += f"""
Date: {log['Date']}
Temperature: {log['Temperature']}
Recorded By: {log['Recorded By']}
─────────────────────────────────────────────────────────────────"""
    
    footer = f"""

Report End
Generated by SPATRAC System
{current_time}
"""
    
    return header + body + footer

def update_product_fields(window, product):
    window['-PRODUCT-'].update(product['Product Code'])
    window['-SUPPLIER_PRODUCT-'].update(product['Supplier Product Code'])
    window['-DEPARTMENT-'].update(product['Department'])

def update_inventory_table(window, inventory):
    window['-INVENTORY_TABLE-'].update([[item['Department'], item['Product Code'], item['Product Description'], item['Quantity'], item['Unit'], item['Status']] for item in inventory])

def show_product_details(product, auth_system):
    # Get the current manager info
    user_info = auth_system.get_current_user_info()
    manager_info = f"Viewed by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Viewed by: N/A"
    
    layout = [
        [sg.Text(f"Product Details: {product['Product Description']}", font=FONT_SUBHEADER)],
        [sg.Text(f"Product Code: {product['Product Code']}")],
        [sg.Text(f"Supplier: {product['Supplier']}")],
        [sg.Text(f"Batch/Lot: {product['Batch/Lot']}")],
        [sg.Text(f"Quantity: {product['Quantity']} {product['Unit']}")],
        [sg.Text(f"Status: {product['Status']}")],
        [sg.Text(f"Current Location: {product['Current Location']}")],
        [sg.Text("Handling History:")],
        [sg.Multiline(product['Handling History'], size=(50, 5), disabled=True)],
        [sg.Text("Temperature Log:")],
        [sg.Multiline('\n'.join(product['Temperature Log']), size=(50, 5), disabled=True)],
        [sg.Text(f"Processed By: {product.get('Processed By', 'N/A')}")],
        [sg.Text("─" * 50)],  # Divider line
        [sg.Text(manager_info, font=('Helvetica', 10, 'italic'))],  # Manager info
        [sg.Button('Close')]
    ]
    window = sg.Window('Product Details', layout)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
    window.close()

def generate_report(inventory, report_type, start_date, end_date, auth_system):
    try:
        if not auth_system or not auth_system.get_current_user_info():
            raise ValueError("User not authenticated")
            
        if report_type == 'Traceability':
            return generate_traceability_report(inventory, start_date, end_date, auth_system)
        elif report_type == 'Inventory Summary':
            return generate_inventory_summary(inventory, start_date, end_date, auth_system)
        elif report_type == 'Temperature Log':
            return generate_temperature_log(inventory, start_date, end_date, auth_system)
        else:
            raise ValueError(f"Invalid report type: {report_type}")
    except Exception as e:
        raise Exception(f"Error generating report: {str(e)}")

def generate_inventory_summary(inventory, start_date, end_date, auth_system):
    try:
        current_user = auth_system.get_current_user_info()
        if not current_user:
            raise ValueError("User information not available")
            
        department = current_user['department']
        
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT product_code, description, quantity, unit, supplier_batch, 
                   sell_by_date, received_date, received_by
            FROM received_products
            WHERE department = ? 
            AND received_date BETWEEN ? AND ?
            AND status = 'active'
            ORDER BY received_date DESC
        ''', (department, start_date, end_date))
        
        inventory_data = cursor.fetchall()
        conn.close()
        
        if not inventory_data:
            return [{
                'Message': 'No inventory data found for the selected period',
                'Department': department,
                'Date Range': f'{start_date} to {end_date}'
            }]
        
        report = []
        for item in inventory_data:
            report.append({
                'Product Code': item[0],
                'Description': item[1],
                'Quantity': item[2],
                'Unit': item[3],
                'Supplier Batch': item[4],
                'Sell By Date': item[5],
                'Received Date': item[6],
                'Received By': item[7],
                'Department': department
            })
        
        return report
    except Exception as e:
        raise Exception(f"Error generating inventory summary: {str(e)}")

def generate_traceability_report(inventory, start_date, end_date, auth_system):
    try:
        current_user = auth_system.get_current_user_info()
        if not current_user:
            raise ValueError("User information not available")
            
        department = current_user['department']
        
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT product_code, description, supplier_batch, sell_by_date, 
                   received_date, received_by, status
            FROM received_products
            WHERE department = ? 
            AND received_date BETWEEN ? AND ?
            ORDER BY received_date DESC
        ''', (department, start_date, end_date))
        
        trace_data = cursor.fetchall()
        conn.close()
        
        if not trace_data:
            return [{
                'Message': 'No traceability data found for the selected period',
                'Department': department,
                'Date Range': f'{start_date} to {end_date}'
            }]
        
        report = []
        for item in trace_data:
            report.append({
                'Product Code': item[0],
                'Description': item[1],
                'Supplier Batch': item[2],
                'Sell By Date': item[3],
                'Received Date': item[4],
                'Received By': item[5],
                'Status': item[6],
                'Department': department
            })
        
        return report
    except Exception as e:
        raise Exception(f"Error generating traceability report: {str(e)}")

def generate_temperature_log(inventory, start_date, end_date, auth_system):
    try:
        current_user = auth_system.get_current_user_info()
        if not current_user:
            raise ValueError("User information not available")
            
        department = current_user['department']
        
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        # Assuming we have a temperature_logs table
        cursor.execute('''
            SELECT recorded_date, temperature, recorded_by
            FROM temperature_logs
            WHERE department = ? 
            AND recorded_date BETWEEN ? AND ?
            ORDER BY recorded_date DESC
        ''', (department, start_date, end_date))
        
        temp_data = cursor.fetchall()
        conn.close()
        
        if not temp_data:
            return [{
                'Message': 'No temperature logs found for the selected period',
                'Department': department,
                'Date Range': f'{start_date} to {end_date}'
            }]
        
        report = []
        for item in temp_data:
            report.append({
                'Date': item[0],
                'Department': department,
                'Temperature': f"{item[1]}°C",
                'Recorded By': item[2]
            })
        
        return report
    except Exception as e:
        raise Exception(f"Error generating temperature log: {str(e)}")

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
    combined_batch = f"{item['Batch/Lot']}-{item['Supplier Batch No']}"
    barcode_image = generate_barcode(combined_batch)
    
    bio = io.BytesIO()
    barcode_image.save(bio, format="PNG")
    barcode_data = bio.getvalue()
    
    layout = [
        [sg.Text(item['Product Description'], font=FONT_NORMAL)],
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
            status TEXT DEFAULT 'active'
        )
    ''')
    
    conn.commit()
    conn.close()

def add_received_product(product, auth_system):
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    current_user = auth_system.get_current_user_info()
    
    cursor.execute('''
        INSERT INTO received_products 
        (product_code, description, quantity, unit, department, received_by, 
         received_date, supplier_batch, sell_by_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        product['Product Code'],
        product['Description'],
        product['Quantity'],
        product['Unit'],
        current_user['department'],
        current_user['username'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        product.get('Supplier Batch', ''),
        product.get('Sell By Date', '')
    ))
    
    conn.commit()
    conn.close()

def get_department_inventory(department):
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT product_code, description, quantity, unit, supplier_batch, 
               sell_by_date, received_date, received_by
        FROM received_products
        WHERE department = ? AND status = 'active'
        ORDER BY received_date DESC
    ''', (department,))
    
    inventory = cursor.fetchall()
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
             sg.CalendarButton('Choose', target='-DB-START-DATE-', format='%Y-%m-%d', 
                             button_color=(COLORS['text'], COLORS['primary']), key='-DB-START-CAL-'),
             sg.Text('To:'), 
             sg.Input(key='-DB-END-DATE-', size=(20,1), default_text=today.strftime('%Y-%m-%d'), enable_events=True),
             sg.CalendarButton('Choose', target='-DB-END-DATE-', format='%Y-%m-%d',
                             button_color=(COLORS['text'], COLORS['primary']), key='-DB-END-CAL-')],
            [sg.Text('Department:'), 
             sg.Combo(['All', 'Butchery', 'Bakery', 'HMR'], default_value='All', key='-DB-DEPT-', size=(20,1))],
            [sg.Text('Product Code:'), sg.Input(key='-DB-PRODUCT-CODE-', size=(20,1))],
            [sg.Button('Search', key='-DB-SEARCH-', button_color=(COLORS['text'], COLORS['primary']))]
        ])],
        [sg.Frame('Results', [
            [sg.Table(
                values=[], 
                headings=['Date', 'Product', 'Department', 'Quantity', 'Status', 'Batch', 'Description'],
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
                SELECT received_date, product_code, department, quantity, status, supplier_batch, description
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
            if values['-DB-PRODUCT-CODE-']:
                query += ' AND product_code LIKE ?'
                params.append(f"%{values['-DB-PRODUCT-CODE-']}%")
                
            cursor.execute(query, params)
            results = cursor.fetchall()
            window['-DB-TABLE-'].update(values=results)
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
                    writer.writerow(['Date', 'Product', 'Department', 'Quantity', 'Status', 'Batch', 'Description'])
                    writer.writerows(window['-DB-TABLE-'].get())
                sg.popup('Success', f'Report saved as {filename}')
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
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt="Database Report", ln=1, align='C')
                
                # Add table headers
                headers = ['Date', 'Product', 'Department', 'Quantity', 'Status', 'Batch', 'Description']
                col_width = 25
                for header in headers:
                    pdf.cell(col_width, 10, txt=header, border=1)
                pdf.ln()
                
                # Add data rows
                for row in window['-DB-TABLE-'].get():
                    for item in row:
                        pdf.cell(col_width, 10, txt=str(item)[:20], border=1)
                    pdf.ln()
                
                pdf.output(filename)
                sg.popup('Success', f'Report saved as {filename}')
            except Exception as e:
                sg.popup_error('Export Error', f'Error saving PDF: {str(e)}')

    elif event == '-DB-VIEW-DETAILS-':
        try:
            selected_rows = window['-DB-TABLE-'].SelectedRows
            if not selected_rows:
                sg.popup_error('No Selection', 'Please select a record to view details.')
                return
            
            table_data = window['-DB-TABLE-'].Values  # Get all table data
            if not table_data:
                sg.popup_error('No Data', 'No data available to view.')
                return
                
            selected_row = table_data[selected_rows[0]]  # Get the selected row data
            if not selected_row:
                sg.popup_error('Invalid Selection', 'Could not retrieve selected record.')
                return
                
            # Create a dictionary with the product details
            product_details = {
                'received_date': selected_row[0],
                'product_code': selected_row[1],
                'department': selected_row[2],
                'quantity': selected_row[3],
                'status': selected_row[4],
                'supplier_batch': selected_row[5],
                'description': selected_row[6] if len(selected_row) > 6 else 'N/A'
            }
            
            show_database_product_details(product_details, auth_system)
        except Exception as e:
            sg.popup_error('Error', f'An error occurred while viewing details: {str(e)}')

def show_database_product_details(product, auth_system):
    """Display product details from database records."""
    user_info = auth_system.get_current_user_info()
    manager_info = f"Viewed by: {user_info['username']} ({user_info['role']} - {user_info['department']})" if user_info else "Viewed by: N/A"
    
    layout = [
        [sg.Text("Product Details", font=FONT_SUBHEADER, justification='center')],
        [sg.Text("─" * 50)],
        [sg.Text(f"Product Code: {product['product_code']}")],
        [sg.Text(f"Department: {product['department']}")],
        [sg.Text(f"Quantity: {product['quantity']}")],
        [sg.Text(f"Status: {product['status']}")],
        [sg.Text(f"Supplier Batch: {product['supplier_batch']}")],
        [sg.Text(f"Received Date: {product['received_date']}")],
        [sg.Text("─" * 50)],
        [sg.Text(manager_info, font=FONT_SMALL)],
        [sg.Button('Close', button_color=(COLORS['text'], COLORS['secondary']), bind_return_key=True)]
    ]
    
    window = sg.Window('Product Details', layout, modal=True, finalize=True, element_justification='center')
    
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Close'):
            break
    
    window.close()

if __name__ == "__main__":
    file_paths = ['Butchery reports Big G.csv', 'Bakery Big G.csv', 'HMR Big G.csv']
    df = load_data(file_paths)
    create_gui(df)