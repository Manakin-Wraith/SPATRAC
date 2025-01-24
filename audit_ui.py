import PySimpleGUI as sg
from datetime import datetime, timedelta
import sqlite3

# Constants for consistent styling
THEME = 'LightGrey1'
FONT_HEADER = ('Helvetica', 24)
FONT_SUBHEADER = ('Helvetica', 18)
FONT_NORMAL = ('Helvetica', 12)
BUTTON_COLOR = ('#FFFFFF', '#2196F3')  # White text on blue background
INPUT_SIZE = (25, 1)

sg.theme(THEME)

def create_audit_tab():
    """
    Create the audit management tab with improved UI/UX.
    """
    product_frame = [
        [sg.Text('Product Information', font=FONT_SUBHEADER)],
        [sg.Text('Product Name:', size=(15,1)), 
         sg.Input(key='-PRODUCT_NAME-', size=INPUT_SIZE)],
        [sg.Text('Batch Code:', size=(15,1)), 
         sg.Input(key='-BATCH_CODE-', size=INPUT_SIZE)],
        [sg.Text('Production Date:', size=(15,1)), 
         sg.Input(key='-PROD_DATE-', size=(15,1)), 
         sg.CalendarButton('Select Date', target='-PROD_DATE-', 
                          format='%Y-%m-%d', button_color=BUTTON_COLOR)],
        [sg.Text('Sell By Date:', size=(15,1)), 
         sg.Input(key='-SELL_BY-', size=(15,1)), 
         sg.CalendarButton('Select Date', target='-SELL_BY-', 
                          format='%Y-%m-%d', button_color=BUTTON_COLOR)],
        [sg.Text('Use By Date:', size=(15,1)), 
         sg.Input(key='-USE_BY-', size=(15,1)), 
         sg.CalendarButton('Select Date', target='-USE_BY-', 
                          format='%Y-%m-%d', button_color=BUTTON_COLOR)],
        [sg.Text('Quantity:', size=(15,1)), 
         sg.Input(key='-QUANTITY-', size=(10,1), enable_events=True)],
        [sg.Text('Start Date:', size=(15,1)), 
         sg.Input(key='-START_DATE-', size=(15,1)), 
         sg.CalendarButton('Select Start Date', target='-START_DATE-', 
                          format='%Y-%m-%d', button_color=BUTTON_COLOR)],
        [sg.Text('End Date:', size=(15,1)), 
         sg.Input(key='-END_DATE-', size=(15,1)), 
         sg.CalendarButton('Select End Date', target='-END_DATE-', 
                          format='%Y-%m-%d', button_color=BUTTON_COLOR)],
    ]

    temperature_frame = [
        [sg.Text('Temperature Monitoring', font=FONT_SUBHEADER)],
        [sg.Text('Temperature (°C):', size=(15,1)), 
         sg.Input(key='-TEMP-', size=(10,1))],
        [sg.Text('Notes:', size=(15,1)), 
         sg.Multiline(key='-TEMP_NOTES-', size=(30,3))],
        [sg.Button('Record Temperature', key='-RECORD_TEMP-', button_color=BUTTON_COLOR)]
    ]

    cleaning_frame = [
        [sg.Text('Cleaning Records', font=FONT_SUBHEADER)],
        [sg.Text('Cleaning Type:', size=(15,1)), 
         sg.Combo(['Daily Clean', 'Deep Clean', 'Equipment Clean'], 
                 key='-CLEAN_TYPE-', size=(20,1))],
        [sg.Text('Details:', size=(15,1)), 
         sg.Multiline(key='-CLEAN_DETAILS-', size=(30,3))],
        [sg.Button('Record Cleaning', key='-RECORD_CLEAN-', button_color=BUTTON_COLOR)]
    ]

    # Main layout combining all frames
    layout = [
        [sg.Text('Audit Management', font=FONT_HEADER)],
        [sg.Column([
            [sg.Frame('Product Details', product_frame)],
            [sg.Frame('Temperature Log', temperature_frame)],
            [sg.Frame('Cleaning Records', cleaning_frame)]
        ])],
        [sg.Button('Save', key='-SAVE-', button_color=BUTTON_COLOR),
         sg.Button('Clear', key='-CLEAR-', button_color=('white', '#FF5252'))]
    ]

    return sg.Tab('Audit Management', layout)

def handle_audit_events(event, values, window, auth_system):
    """
    Handle events from the audit management tab.
    """
    if event == '-RECORD_TEMP-':
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO temperature_logs (
                    product_id,
                    temperature,
                    recorded_by,
                    notes
                ) VALUES (?, ?, ?, ?)
            ''', (
                values['-PRODUCT_NAME-'],
                float(values['-TEMP-']),
                auth_system.current_user.username,
                values['-TEMP_NOTES-']
            ))
            conn.commit()
            sg.popup('Temperature recorded successfully!', title='Success')
            
            # Clear temperature inputs
            window['-TEMP-'].update('')
            window['-TEMP_NOTES-'].update('')
            
        except Exception as e:
            sg.popup_error(f'Error recording temperature: {str(e)}', title='Error')
        finally:
            conn.close()

    elif event == '-RECORD_CLEAN-':
        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO cleaning_records (
                    department,
                    cleaning_date,
                    cleaning_type,
                    cleaned_by,
                    cleaning_details
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                auth_system.current_user.department,
                datetime.now().strftime('%Y-%m-%d'),
                values['-CLEAN_TYPE-'],
                auth_system.current_user.username,
                values['-CLEAN_DETAILS-']
            ))
            conn.commit()
            sg.popup('Cleaning record saved successfully!', title='Success')
            
            # Clear cleaning inputs
            window['-CLEAN_TYPE-'].update('')
            window['-CLEAN_DETAILS-'].update('')
            
        except Exception as e:
            sg.popup_error(f'Error recording cleaning: {str(e)}', title='Error')
        finally:
            conn.close()

    elif event == '-SAVE-':
        # Validate inputs
        if not all([values['-PRODUCT_NAME-'], values['-BATCH_CODE-'], 
                   values['-PROD_DATE-'], values['-SELL_BY-'], 
                   values['-QUANTITY-'], values['-START_DATE-'], 
                   values['-END_DATE-']]):
            sg.popup_error('Please fill in all required fields', title='Validation Error')
            return

        conn = sqlite3.connect('spatrac.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO products (
                    product_name,
                    final_product_batch_code,
                    production_date,
                    sell_by_date,
                    use_by_date,
                    quantity_produced,
                    department,
                    created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                values['-PRODUCT_NAME-'],
                values['-BATCH_CODE-'],
                values['-PROD_DATE-'],
                values['-SELL_BY-'],
                values['-USE_BY-'],
                int(values['-QUANTITY-']),
                auth_system.current_user.department,
                auth_system.current_user.username
            ))
            conn.commit()
            sg.popup('Product saved successfully!', title='Success')
            
            # Clear product inputs
            for key in ['-PRODUCT_NAME-', '-BATCH_CODE-', '-PROD_DATE-', 
                       '-SELL_BY-', '-USE_BY-', '-QUANTITY-', '-START_DATE-', '-END_DATE-']:
                window[key].update('')
                
        except Exception as e:
            sg.popup_error(f'Error saving product: {str(e)}', title='Error')
        finally:
            conn.close()

    elif event == '-CLEAR-':
        # Clear all inputs
        for key in window.AllKeysDict:
            if isinstance(window[key], sg.Input) or isinstance(window[key], sg.Multiline):
                window[key].update('')
