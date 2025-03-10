import random
from app import supabase
import os
from werkzeug.utils import secure_filename
from app.controllers import user_controller
from app.controllers import notifications_controller
from app.utils.email_service import EmailService
from app.controllers.eth_account_controller import get_token_balance


# Create a new company
def create_company(
    company_id,
    company_name,
    company_phone_number,
    company_email,
    company_industry,
    company_country,
    company_city,
    company_address,
    company_description,
    sender_email,  # Add sender_email parameter
    company_website=None,
    company_image=None
):
    try:
        # Generate unique company ID
        
        # Prepare company data
        company_data = {
            'company_id': company_id,
            'company_name': company_name,
            'company_phone_number': company_phone_number,
            'company_email': company_email,
            'company_industry': company_industry,
            'company_country': company_country,
            'company_city': company_city,
            'company_address': company_address,
            'company_description': company_description,
            'company_website': company_website,
            'status': False
        }

        # Upload image first if provided
        if company_image:
            image_url = upload_company_image(company_id, company_image)
            if image_url:
                company_data['company_image'] = image_url
            else:
                print("Failed to upload company logo")

        # Insert company into database
        response = supabase.table('companies').insert(company_data).execute()
        
        if response.data:
            try: 
                admin_response = supabase.table('roles').select('user_id').eq('admin', True).execute()
                if not admin_response.data:
                    print("No admin users found")
                    return False

                # Get admin emails
                admin_ids = [admin['user_id'] for admin in admin_response.data]
                admin_users = supabase.table('user').select('email').in_('id', admin_ids).execute()
                
                if not admin_users.data:
                    print("Could not fetch admin emails")
                    return False

                # Create notifications for each admin
                for admin in admin_users.data:
                    if notifications_controller.create_notification('company_registration', sender_email, admin['email'], company_id):
                        return {'success': True, 'company_id': company_id}
                    else:
                        print("Warning: Failed to create admin notifications")
                        return {'success': True, 'company_id': company_id, 'warning': 'Failed to notify admins'}
                    
            except Exception as e:
                print(f"Error creating registration notifications: {e}")
                return {'success': True, 'company_id': company_id, 'warning': 'Failed to notify admins'}  
              
        return {'success': False, 'error': 'Failed to create company'}

    except Exception as e:
        print(f"Error creating company: {e}")
        return {'success': False, 'error': str(e)}

def send_admin_notification(user_info, company_data):
    email_service = EmailService()
    email_service.send_admin_notification(user_info, company_data)
    if email_service:
        return True
    else:
        return False

# Upload company image to Supabase storage
def upload_company_image(company_id, image_file):
    try:
        original_filename = secure_filename(image_file.filename)
        file_extension = os.path.splitext(original_filename)[1]
        new_filename = f"company_{company_id}{file_extension}"

        try:
            existing_images = supabase.storage.from_('company_logos').list()
            for item in existing_images:
                if f"company_{company_id}" in item['name']:
                    supabase.storage.from_('company_logos').remove([item['name']])
                    break
        except Exception as e:
            print(f"Warning when checking existing image: {e}")

        file_content = image_file.read()
        image_file.seek(0)  # Reset file pointer after reading

        
        response = supabase.storage.from_('company_logos').upload(
            path=new_filename,
            file=file_content,
            file_options={"content-type": image_file.content_type}
        )

        if response:
            
            public_url = supabase.storage.from_('company_logos').get_public_url(new_filename)
            print(f"Image uploaded successfully: {public_url}")
            return public_url

        print("Upload response failed:", response)
        return None

    except Exception as e:
        print(f"Error uploading image: {e}")
        return None

# Get company by ID
def get_company_by_id(company_id):
    try:
        response = supabase.table('companies').select('*').eq('company_id', company_id).execute()
        if len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting company: {e}")
        return None

# Get company by name
def get_id_admin_by_company(company_id):  
    try:
        response = supabase.table('company_employe').select('user_id').eq('company_id', company_id).eq('company_admin', True).execute()
        if len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting company: {e}")
        return None

# Get admin info by company ID
def get_admin_info_by_company(company_id):
    try:
        
        admin_ids_response = supabase.table('company_employe').select('user_id').eq('company_id', company_id).eq('company_admin', True).execute()
        
        if len(admin_ids_response.data) == 0:
            return []  
        
        admin_info_list = []
        
        for admin in admin_ids_response.data:
            user_info = user_controller.get_user_by_id(admin['user_id'])
            if user_info:  
                admin_info_list.append(user_info)
        
        return admin_info_list
    
    except Exception as e:
        print(f"Error getting admin info for company {company_id}: {e}")
        return None

# Get company ID by owner
def get_companyID_by_owner(user_id):
    try:
        # Query to get company IDs where the user is a company admin
        response = supabase.table('company_employe') \
            .select('company_id') \
            .eq('user_id', user_id) \
            .eq('company_admin', True) \
            .execute()
        
        if response.data:
            # Return the list of company IDs where the user is a company admin
            return response.data
        else:
            return "No companies found where the user is an admin."
    except Exception as e:
        print(f"Error checking user ownership: {e}")
        return []

# Check if company exists
def check_company_exists(company_name):
    try:
        response = supabase.table('companies').select('company_name').eq('company_name', company_name).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking company: {e}")
        return False

# Get all pending companies
def get_pending_companies():
    try:
        result = supabase.from_('companies').select('*').eq('status', False).execute() 
        return result.data
    except Exception as e:
        print(f"Error fetching pending companies: {e}")
        return []
    
# Approve company
def approve_company(sender_email, receiver_email, company_id):
    try:
        result = supabase.from_('companies').update({'status': True}).eq('company_id', company_id).execute()
        if result.data:


            user = user_controller.get_user_by_email(receiver_email)
            if user:
                user_id = user.get('id')
                admin_response = supabase.from_('company_employe').insert({
                    'user_id': user_id,
                    'company_id': company_id,
                    'company_admin': True
                }).execute()
                if not admin_response.data:
                    print("Failed to set user as company admin")
                    return False
            else:
                print("User not found for receiver email")
                return False
                
            notifications_controller.create_notification('acception registration company', sender_email, receiver_email, company_id)
            email_service = EmailService()
            email_service.send_company_approved_notification(to_email=receiver_email)
            return True
        else:
            return False
    except Exception as e:
        print(f"Error approving company: {e}")
        return False

# Delete company notification 
def delete_company_notification(sender_email, company_id):
    try:
        admin_response = supabase.table('roles').select('user_id').eq('admin', True).execute()
        if not admin_response.data or len(admin_response.data) == 0:
            print("No admin found")
            return False

        admin_id = admin_response.data[0]['user_id']

        user_response = supabase.table('user').select('email').eq('id', admin_id).execute()
        if not user_response.data or len(user_response.data) == 0:
            print("Admin email not found")
            return False
        
        receiver_email = user_response.data[0]['email']
        notifications_controller.create_notification('company_elimination', sender_email, receiver_email, company_id)
        return True
    except Exception as e:
        print(f"Error deleting company notification: {e}")
        return False

# Eliminate company
def eliminate_company(sender_email, receiver_email, company_id):
    try:
        success = delete_company(company_id)
        if success:
            notifications_controller.create_notification('acception elimination company', sender_email, receiver_email, company_id)
            return True
        else: False
    except Exception as e:
        print(f"Error eliminating company: {e}")
        return False

# Reject company
def reject_company(sender_email, receiver_email, company_id):
    try:
        success = delete_company(company_id)
        if success:
            notifications_controller.create_notification('rejection registration company', sender_email, receiver_email, company_id)
            return True
        else: False
    except Exception as e:
        print(f"Error rejecting company: {e}")
        return False

# Delete company    
def delete_company(company_id):
    try:
        company = get_company_by_id(company_id)
        filename = None
        if company and company.get('company_image'):
            image_url = company['company_image']
            filename = image_url.split('/')[-1].split('?')[0]
                
        result = supabase.from_('companies').delete().eq('company_id', company_id).execute()
        if result and filename:
            storage_response = supabase.storage.from_('company_logos').remove([filename])
        if result and storage_response:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error deleting company: {e}")
        return False

# Search companies
def search_companies(search_term):
    try:
        response = supabase.table('companies') \
            .select('*') \
            .ilike('company_name', f'%{search_term}%') \
            .eq('status', True) \
            .execute()
        return response.data
    except Exception as e:
        print(f"Error searching companies: {e}")
        return []

# Get all companies sorted
def get_all_companies_sorted():
    try:
        response = supabase.table('companies') \
            .select('*') \
            .eq('status', True) \
            .order('company_name') \
            .execute()
        return response.data
    except Exception as e:
        print(f"Error getting sorted companies: {e}")
        return []

# Update company
def update_company(company_id, company_name, company_phone_number, company_email, company_industry, company_website, company_description, company_image):
    try:

        update_data = {
            'company_name': company_name,
            'company_phone_number': company_phone_number,
            'company_email': company_email,
            'company_industry': company_industry,
            'company_website': company_website,
            'company_description': company_description
        }

        if company_image:
            update_data['company_image'] = company_image

        update_response = supabase.table('companies') \
            .update(update_data) \
            .eq('company_id', company_id) \
            .execute()

        if update_response.data:
            return {'success': True, 'message': 'Company updated successfully'}
        else:
            return {'success': False, 'message': 'No changes made to the company'}

    except Exception as e:
        print(f"Error updating company in Supabase: {e}")
        return {'success': False, 'message': 'Error updating the company in the database'}


# Get all company images
def get_all_company_images():
    try:
        response = supabase.table('companies') \
            .select('company_image') \
            .eq('status', True) \
            .execute()

        image_urls = [company['company_image'] for company in response.data if company.get('company_image')]

        return image_urls
    except Exception as e:
        print(f"Error getting company images: {e}")
        return []

# Update all companies token balances
def update_all_companies_token_balances():

    try:
        # Get all companies with ETH addresses
        companies = get_all_companies_with_eth_address()
        
        for company in companies:
            if company.get('eth_address'):
                # Get current token balance from blockchain
                current_balance = get_token_balance(company['eth_address'])
                
                # Update token balance in database
                supabase.table('companies') \
                    .update({'token': current_balance}) \
                    .eq('company_id', company['company_id']) \
                    .execute()
        return True
    except Exception as e:
        print(f"Error updating companies token balances: {e}")
        return False

# Get top companies by token balance
def get_top_companies():

    try:
        update_all_companies_token_balances()
        # Get companies sorted by token balance
        response = supabase.table('companies') \
            .select('*') \
            .eq('status', True) \
            .order('token', desc=True) \
            .limit(3) \
            .execute()

        return response.data if response.data else []

    except Exception as e:
        print(f"Error getting top companies: {e}")
        return []
    
# Check if ETH address is unique
def check_eth_address_unique(eth_address, exclude_company_id=None):
    try:
        query = supabase.table('companies').select('company_id').eq('eth_address', eth_address)
        if exclude_company_id:
            query = query.neq('company_id', exclude_company_id)
        response = query.execute()
        return len(response.data) == 0
    except Exception as e:
        print(f"Error checking ETH address uniqueness: {e}")
        return False

# Update company ETH address
def update_company_eth_address(company_id, eth_address):
    try:
        # Check if the ETH address is unique (excluding current company)
        if not check_eth_address_unique(eth_address, company_id):
            return False
            
        # Update the company's ETH address
        response = supabase.table('companies').update({
            'eth_address': eth_address
        }).eq('company_id', company_id).execute()
        
        return bool(response.data)
        
    except Exception as e:
        print(f"Error updating company ETH address: {e}")
        return False

# Get all companies with ETH addresses
def get_all_companies_with_eth_address():
    try:
        result = supabase.from_('companies') \
            .select('*') \
            .filter("eth_address", "neq", "no address") \
            .filter("eth_address", "neq", None) \
            .filter("eth_address", "neq", "") \
            .execute()

        # Return the data or empty list if no results
        return result.data if result.data else []

    except Exception as e:
        print(f"Error getting companies with ETH addresses: {e}")
        return []

# Get company by ETH address
def get_company_by_eth_address(eth_address):
    try:
        response = supabase.table('companies').select('*').eq('eth_address', eth_address).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting company by ETH address: {e}")
        return None

# Create token request notification
def create_token_request_notification(sender_email, sender_company_id ,receiver_company_id, amount, same_request):
    try:

        # Get receiver company admins
        admin_response = supabase.table('company_employe').select('user_id').eq('company_id', receiver_company_id).eq('company_admin', True).execute()
        if not admin_response.data:
            return False

        # Create notification for each admin
        for admin in admin_response.data:
            user = user_controller.get_user_by_id(admin['user_id'])
            if user:
                success = notifications_controller.create_notification(
                    type='token_request',
                    sender=sender_email,
                    receiver=user['email'],
                    company_id=receiver_company_id,
                    amount=amount,
                    same_request=same_request,
                    sender_company_id=sender_company_id
                )
                if not success:
                    return False

        return True
    except Exception as e:
        print(f"Error creating token request notification: {e}")
        return False

# Get all products
def get_products():
    try:
        response = supabase.table('products') \
            .select('*') \
            .execute()
        return response.data
    except Exception as e:
        print(f"Error getting products: {e}")
        return []
    
# Get product by company ID
def get_product_by_company_id(company_id):
    try:    
        response2 = supabase.table('products') \
            .select('*') \
            .eq('company_id', company_id)\
            .execute()
        if response2.data:
            merged_data = []

            for item2 in response2.data:
                merged_item = {**item2} 
                merged_data.append(merged_item)

            return merged_data
        else:
            print("Nessun dato trovato in una delle risposte.")
            return []

    except Exception as e:
        print(f"Errore nel recupero dei prodotti: {e}")
        return []

# Get products by company ID   
def get_products_by_company_id(company_id):
    try:
        response = supabase.table('chain_products') \
            .select('*')\
            .or_('farmer.eq.' + str(company_id) +',transporter1.eq.' + str(company_id) + ',transporter2.eq.' + str(company_id) + ',transformer.eq.' + str(company_id) + ',seller.eq.' + str(company_id)) \
            .execute()
        

        response2 = supabase.table('products') \
            .select('*') \
            .execute()
        if response.data and response2.data:
            merged_data = []

            for item1 in response.data:
                for item2 in response2.data:

                    if item1['id'] == item2['id']:
                        merged_item = {**item1, **item2}  
                        merged_data.append(merged_item)

            return merged_data
        else:
            print("Nessun dato trovato in una delle risposte.")
            return []

    except Exception as e:
        print(f"Errore nel recupero dei prodotti: {e}")
        return []

# Update product in products table  
def update_product_in_products_table(product_id, updated_data):
    try:
        old_value = supabase.table('products') \
            .select('*') \
            .eq('id', product_id)\
            .execute()
        old_quantity=old_value.data[0]['quantity']
        updata=int(updated_data['quantity'])
        if old_quantity<updata:
            difference= updata-old_quantity
            
            emission_difference=farmer_emission(difference)
           
            emission= old_value.data[0]['co2_emission']+ emission_difference
            
            new_quantity= int(old_value.data[0]['total_quantity'])+difference
          
            updated_data_new = {
                'name': updated_data['name'],
                'description': updated_data['description'],
                'quantity': updata,
                'co2_emission' : emission,
                'total_quantity' : new_quantity
            }
            companies_emission(old_value.data[0]['company_id'], emission_difference, difference)

        else:
            updated_data_new=updated_data
               
        response = supabase.table('products') \
            .update(updated_data_new) \
            .eq('id', product_id) \
            .execute()

        if response:
            return True
        else:
            print(f"Errore nell'aggiornamento del prodotto con ID {product_id}.")
            return False

    except Exception as e:
        print(f"Errore nell'aggiornamento del prodotto con ID {product_id}: {e}")
        return False

# Update total quantity and CO2 emission
def update_total_quantity_co2_emission_processor(product_request_id):
    try:
        response = supabase.table('product_request') \
                            .select('*') \
                            .eq('id', product_request_id) \
                            .execute()
        quantity_to_insert=response.data[0]['quantity']
        product_id=response.data[0]['id_product']
        
        old_value = supabase.table('products') \
                .select('*') \
                .eq('id', product_id)\
                .execute()
        
        old_quantity=old_value.data[0]['total_quantity']
       
        new_total_quantity=old_quantity+quantity_to_insert
        
        co2_to_insert=processor_emission(quantity_to_insert)
        
        new_co2=old_value.data[0]['co2_emission']+co2_to_insert

        updated_data_new = {
                    'co2_emission' : new_co2,
                    'total_quantity' : new_total_quantity
                }
                
        response1 = supabase.table('products') \
                .update(updated_data_new) \
                .eq('id', product_id) \
                .execute()
        
        companies_emission(old_value.data[0]['company_id'],  new_co2, new_total_quantity)

        if response1:
            return True
        else:
            print(f"Errore nell'aggiornamento del prodotto con ID {product_id}.")
            return False

    except Exception as e:
        print(f"Errore nell'aggiornamento del prodotto con ID {product_id}: {e}")
        return False
    
# Get type of company by ID
def type_of_company_by_id(company_id):
    try:
        
        response = supabase.table('companies') \
        .select('company_industry')\
        .eq('company_id', company_id)\
        .execute()
        
        return response
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

# Calculate emissions
def farmer_emission(product_quantity):
    average_emission = round(random.uniform(0.5, 20), 2)
    emission = int(product_quantity)*average_emission
    return emission

# Calculate emissions
def processor_emission(product_quantity):
    average_emission = round(random.uniform(1, 20), 2)
    emission = int(product_quantity)*average_emission
    return emission

# Calculate emissions
def transporter_emission(product_quantity):
    average_emission = round(random.uniform(0.1, 0.4), 2)
    emission = int(product_quantity)*average_emission
    return emission

# Calculate emissions
def seller_emission(product_quantity):
    average_emission = round(random.uniform(0.1, 2), 2)
    emission = int(product_quantity)*average_emission
    return emission

# Update company emissions
def companies_emission(company_id, new_emission, new_quantity):
    try:
        emission_company=supabase.table('companies').select('*').eq('company_id', company_id).execute()
        emission=emission_company.data[0]['co2_emission']+ new_emission
        quantity=int(emission_company.data[0]['total_quantity'])+ int(new_quantity)
        supabase.table('companies').update([{
                'co2_emission': emission,
                'total_quantity': quantity
            }])\
        .eq('company_id', company_id).execute()

    except Exception as e:
        return {'error': str(e)}

# Create new product by farmer
def new_product_by_farmer(company_id, product_name, product_description, product_quantity):
    try:
        product_name = product_name.strip() 
        product_name = ''.join(e for e in product_name if e.isalnum() or e.isspace()) 
        product_name = product_name.lower()
        existing_product = supabase.table('products').select('id').eq('company_id', company_id).eq('name', product_name).execute()

        if existing_product.data:
            return False

        emission=farmer_emission(product_quantity)
        
        response = supabase.table('products').insert([{
            'name': product_name,
            'description': product_description,
            'quantity': product_quantity,
            'company_id': company_id,
            'total_quantity' : product_quantity,
            'co2_emission' : emission
        }]).execute()

        companies_emission(company_id, emission, product_quantity)

        if response.data:
            product_id = response.data[0]['id']

            supabase.table('chain_products').insert([{
                'id': product_id,
                'farmer': company_id
            }]).execute()

            return True
        else:
            return {'error': 'Errore nell\'inserimento del prodotto.'}

    except Exception as e:
        return {'error': str(e)}



# Delete product
def delete_product(product_id):
    try:
        response = supabase.table('products').delete().eq('id', product_id).execute() 
        return response
    except Exception as e:
        print(f"Error getting products: {e}")
        return False
    
# Create new product by processor
def new_product_by_processor(company_id, product_name, product_description, product_quantity):
    try:
        product_name = product_name.strip()
        product_name = ''.join(e for e in product_name if e.isalnum() or e.isspace())
        product_name = product_name.lower()
        existing_product = supabase.table('products').select('id').eq('company_id', company_id).eq('name', product_name).execute()

        if existing_product.data:
            return False

        response = supabase.table('products').insert([{
            'name': product_name,
            'description': product_description,
            'quantity': product_quantity,
            'company_id': company_id
        }]).execute()

        if response.data:
            product_id = response.data[0]['id']

            supabase.table('chain_products').insert([{
                'id': product_id,
                'transformer': company_id
            }]).execute()

            return True
        else:
            return {'error': 'Errore nell\'inserimento del prodotto.'}

    except Exception as e:
        return {'error': str(e)}

# Get companies by industry 
def get_companies_by_industry(company_industry):
    try:
        response = supabase.table('companies') \
            .select('*')\
            .eq('company_industry', company_industry) \
            .eq('status', True)\
            .execute()
        
        return response.data
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    
# Create product request
def create_product_request(id_buyer, id_supplier, id_product, id_raw_material, quantity, quantity_of_raw_material, 
                           id_transporter, transport_date, distance_to_travel):
    supplier_approve=None
    transporter_approve=None

    data = {
        "id_buyer": id_buyer,
        "id_supplier": id_supplier,
        "id_product": id_product,
        "id_raw_material" : id_raw_material,
        "quantity": quantity,
        "quantity_of_raw_material": quantity_of_raw_material,
        "id_transporter": id_transporter,
        "transport_date": transport_date,
        "distance_to_travel": distance_to_travel,
        "supplier_approve": supplier_approve,
        "transporter_approve": transporter_approve,
    }

    response = supabase.table('product_request').insert(data).execute()

    return response

# Get owners by company ID
def get_owners_by_company(company_id):
    try:
        employees_response = supabase.table('company_employe')\
            .select('user_id')\
            .eq('company_id', company_id)\
            .eq('company_admin', True)\
            .execute()
        
        if not employees_response.data:
            return []

        user_ids = [employee['user_id'] for employee in employees_response.data]

        users_response = supabase.table('user')\
            .select('*')\
            .in_('id', user_ids)\
            .execute()

        return [{'company_id': company_id, **user} for user in users_response.data] if users_response.data else []
    
    except Exception as e:
        print(f"Error getting company owners: {e}")
        return []

# Get product request by ID
def get_product_request_by_id(product_request_id):
    response = supabase.table('product_request').select('*').eq('id', product_request_id).execute()

    if response.data:
        return response.data[0] 
    else:
        return None 

# Get products by ID
def get_products_by_id(product_id):
    try:
        response = supabase.table('products') \
            .select('*') \
            .eq('id', product_id)\
            .execute()
        
        if response.data:
            product = response.data[0]  # Get the first product (if there are any)
            return product  # Return just the product data
        else:
            return None 
        

    except Exception as e:
        print(f"Error getting products: {e}")
        return []

# Approve supplier   
def approve_supplier(product_request_id):
    response = supabase.table('product_request').update({'supplier_approve': True}).eq('id', product_request_id).execute()

    if response:
        return True
    else:
        return False
    
# Approve transporter
def approve_transporter(product_request_id):
    response = supabase.table('product_request').update({'transporter_approve': True}).eq('id', product_request_id).execute()

    if response:
        return True
    else:
        return False

# Reject supplier
def reject_supplier(product_request_id):
    response = supabase.table('product_request').update({'supplier_approve': False}).eq('id', product_request_id).execute()

    if response:
        return True
    else:
        return False
    
# Reject transporter
def reject_transporter(product_request_id):
    response = supabase.table('product_request').update({'transporter_approve': False}).eq('id', product_request_id).execute()

    if response:
        return True
    else:
        return False
    
# Check supplier approval
def check_supplier_approve(product_request_id):
    response = supabase.table('product_request').select('quantity_of_raw_material').eq('supplier_approve', True).eq('id', product_request_id).execute()
    
    return response  

# Get product ID from request
def id_product_from_request(product_request_id):
    try:
        response = supabase.table('product_request').select('id_product').eq('id', product_request_id).execute()
        return response
  
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

# Update quantity after reject   
def update_quantity_after_reject(product_id, new_quantity):
    try:
        response = supabase.table('products').select('quantity').eq('id', product_id).execute()
        quantity=response.data[0]['quantity'] + new_quantity
        update=supabase.table('products').update({'quantity': quantity}).eq('id', product_id).execute()

        if update:
            return True
        else:
            return False 
        
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

# Check approval status   
def check_approval_status(product_request_id):
    response = supabase.table('product_request').select('supplier_approve', 'transporter_approve').eq('id', product_request_id).execute()

    if response and response.data:
        approval_data = response.data[0]
        supplier_approve = approval_data['supplier_approve']
        transporter_approve = approval_data['transporter_approve']

        if supplier_approve and transporter_approve:
            return True
        else:
            return False
    else:
        return False
    
# Check if product and raw material are the same
def check_equal_status_of_request_product(product_request_id):
    
    response = supabase.table('product_request').select('id_raw_material', 'id_product').eq('id', product_request_id).execute()
    if response:
        approval_data = response.data[0]
        id_raw_material = approval_data['id_raw_material']
        id_product = approval_data['id_product']

        if id_product == id_raw_material:
            return True  
        else:
            return False  
    else:
        return False  

# Update product quantity after approval    
def update_product_quantity_after_approval(product_request_id):
    response = supabase.table('product_request') \
                        .select('quantity_of_raw_material', 'id_raw_material') \
                        .eq('id', product_request_id) \
                        .execute()
    if response:
        product_request_data = response.data[0]
        quantity_to_deduct = product_request_data['quantity_of_raw_material']
        id_raw_material = product_request_data['id_raw_material']

        product_response = supabase.table('products') \
                                    .select('quantity') \
                                    .eq('id', id_raw_material) \
                                    .execute()

        if product_response:
            product_data = product_response.data[0]
            current_quantity = product_data['quantity']


            new_quantity = current_quantity - quantity_to_deduct

            update_response = supabase.table('products') \
                                        .update({'quantity': new_quantity}) \
                                        .eq('id', id_raw_material) \
                                        .execute()

            if update_response:
                return True
            else:
                return False
        else:
            return False
    else:
        return False


# Update quantity of processed product  
def update_quantity_of_processed_product(product_request_id):

    response = supabase.table('product_request') \
                        .select('quantity', 'id_product') \
                        .eq('id', product_request_id) \
                        .execute()
    
    if response:
        product_request_data = response.data[0]
        quantity_to_deduct = product_request_data['quantity']
        id_processed_material = product_request_data['id_product']

        product_response = supabase.table('products') \
                                    .select('quantity') \
                                    .eq('id', id_processed_material) \
                                    .execute()
        
        if product_response:
            product_data = product_response.data[0]
            current_quantity = product_data['quantity']

            new_quantity = current_quantity + quantity_to_deduct

            update_response = supabase.table('products') \
                                        .update({'quantity': new_quantity}) \
                                        .eq('id', id_processed_material) \
                                        .execute()
            
            if update_response:
                return True
            else:
                return False
        else:
            return False
    else:
        return False

# Add transport record from product request
def add_transport_record_from_product_request(product_request_id):

    response = supabase.table('product_request') \
                        .select('id_buyer', 'id_supplier', 'id_transporter', 'distance_to_travel','id_product', 'transport_date') \
                        .eq('id', product_request_id) \
                        .execute()
    
    if response:
        product_request_data = response.data[0]
        id_buyer = product_request_data['id_buyer']
        id_seller = product_request_data['id_supplier']
        id_transporter = product_request_data['id_transporter']
        distance_to_travel = product_request_data['distance_to_travel']
        transport_date = product_request_data['transport_date']
        id_product= product_request_data['id_product']
        co2_emission=transporter_emission(distance_to_travel)

        new_transport_data = {
            'id_buyer': id_buyer,
            'id_seller': id_seller,
            'id_transporter': id_transporter,
            'distance': distance_to_travel,
            'date_delivery': transport_date,
            'id_product' : id_product,
            'co2_emission' : co2_emission
        }

        companies_emission(id_transporter, co2_emission, distance_to_travel)
       
        insert_response = supabase.table('transport').insert(new_transport_data).execute()
        if insert_response:
            return insert_response.data[0]['id']
        else:
            return False
    else:
        return False
    
# Update or insert chain product   
def update_or_insert_chain_product(product_request_id):

    response = supabase.table('product_request') \
                        .select('id_product', 'id_transporter', 'id_supplier', 'id_buyer') \
                        .eq('id', product_request_id) \
                        .execute()

    if response:
        product_request_data = response.data[0]
        id_product = product_request_data['id_product']
        id_transporter = product_request_data['id_transporter']
        id_supplier = product_request_data['id_supplier']
        id_buyer = product_request_data['id_buyer']


        chain_product_response = supabase.table('chain_products') \
                                         .select('id', 'farmer', 'transporter1', 'transformer') \
                                         .eq('id', id_product) \
                                         .execute()

        if chain_product_response and chain_product_response.data:
            for chain_product in chain_product_response.data:
                farmer = chain_product['farmer']
                transporter1 = chain_product['transporter1']


                if farmer is None and transporter1 is None:
                    update_response = supabase.table('chain_products') \
                                              .update({
                                                  'farmer': id_supplier,
                                                  'transporter1': id_transporter
                                              }) \
                                              .eq('id', id_product) \
                                              .execute()
                
                    return bool(update_response)


                if farmer == id_supplier and transporter1 == id_transporter:
                    return True


            insert_response = supabase.table('chain_products') \
                                      .insert({
                                          'id': id_product,
                                          'farmer': id_supplier,
                                          'transporter1': id_transporter,
                                          'transformer': id_buyer
                                      }) \
                                      .execute()

            return bool(insert_response)
        else:

            insert_response = supabase.table('chain_products') \
                                      .insert({
                                          'id': id_product,
                                          'farmer': id_supplier,
                                          'transporter1': id_transporter,
                                          'transformer': id_buyer
                                      }) \
                                      .execute()

            return bool(insert_response)
    else:
        return False

# Update or insert chain product for seller
def update_or_insert_chain_product_for_seller(product_request_id):

    response = supabase.table('product_request') \
                        .select('id_product', 'id_transporter', 'id_supplier', 'id_buyer') \
                        .eq('id', product_request_id) \
                        .execute()
    
    if response:
        product_request_data = response.data[0]
        id_product = product_request_data['id_product']
        id_transporter = product_request_data['id_transporter']
        
        id_buyer = product_request_data['id_buyer']

        chain_product_response = supabase.table('chain_products') \
                                         .select('id', 'farmer', 'transporter2', 'transporter1','transformer', 'seller') \
                                         .eq('id', id_product) \
                                         .execute()

        for chain_product in chain_product_response.data:
            farmer = chain_product['farmer']
            transporter2 = chain_product['transporter2']
            transformer = chain_product['transformer']
            transporter1 = chain_product['transporter1']
            seller = chain_product['seller']

            if seller == id_buyer and transporter2 == id_transporter:
                return True
            
            if seller is None and transporter2 is None:
                update_response = supabase.table('chain_products') \
                                    .insert({
                                        'id': id_product,
                                        'farmer': farmer,
                                        'transporter2': id_transporter,
                                        'seller': id_buyer,
                                        'transformer' : transformer,
                                        'transporter1' : transporter1
                                    }) \
                                    .execute()
            
                return bool(update_response)
    
    else:
        return False

# Insert product seller
def insert_product_seller(product_request_id):
   
    response = supabase.table('product_request') \
                        .select('id_product', 'id_buyer', 'quantity') \
                        .eq('id', product_request_id) \
                        .execute()

    if response:
        product_request_data = response.data[0]
        id_product = product_request_data['id_product']
        id_buyer = product_request_data['id_buyer']
        quantity =  product_request_data['quantity']
        co2=seller_emission(quantity)


        response2 = supabase.table('seller_products') \
                            .select('id','id_seller', 'quantity', 'co2_emission', 'total_quantity') \
                            .eq('id_product', id_product) \
                            .eq('id_seller', id_buyer)\
                            .execute()
        
        if response2.data:
            old_product = response2.data[0]
            
            old_quantity = old_product['quantity']
            
            old_co2 = old_product['co2_emission']
            
            old_total_quantity = old_product['total_quantity']
           
            id_old_product=old_product['id']

            new_quantity = old_quantity + quantity
            new_co2 = old_co2 + co2
            new_total_quantity = old_total_quantity + quantity
            update_response = supabase.table('seller_products') \
                                              .update({
                                                'quantity': new_quantity,
                                                'co2_emission': new_co2,
                                                'total_quantity' : new_total_quantity
                                              }) \
                                              .eq('id', id_old_product) \
                                              .execute() 

            
            companies_emission(id_buyer,  new_co2, new_total_quantity)
    
        else:
            update_response = supabase.table('seller_products') \
                                    .insert({
                                        'id_product': id_product,
                                        'id_seller' : id_buyer,
                                        'quantity' : quantity,
                                        'co2_emission' : co2,
                                        'total_quantity' : quantity
                                    }) \
                                    .execute()
            companies_emission(id_buyer,  co2, quantity)
            
        return bool(update_response)
    else:
        return False
    
# Get products by seller
def get_products_by_seller(company_id):
    try:
        response = supabase.table('seller_products') \
                            .select('*') \
                            .eq('id_seller', company_id) \
                            .execute()
        return response
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

# Get information by product ID    
def get_information_by_id_product(product_id):
    try:
        response = supabase.table('products') \
                            .select('id, name, description') \
                            .eq('id', product_id) \
                            .execute()
        return response
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

# Get information of transporter    
def get_information_of_transporter(company_id):
    try:
        response = supabase.table('transport') \
                            .select('*') \
                            .eq('id_transporter', company_id) \
                            .execute()
        return response
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

# Update quantity of seller   
def update_quantity_of_seller(id, quantity):
    try:
        
        response= supabase.table('seller_products')\
                            .update({
                                'quantity': quantity,})\
                            .eq('id_product', id)\
                            .execute()
        
        return response
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

# Delete product of seller   
def delete_product_of_seller(product_id):
    try:
        response = supabase.table('seller_products').delete().eq('id_product', product_id).execute() 
        return response
    except Exception as e:
        print(f"Error getting products: {e}")
        return []
    
# Get companies of chain product
def get_companies_of_chain_product(product_id, company_id):
    try:
        response = supabase.table('chain_products').select('*').eq('id', product_id).eq('seller',company_id).execute() 
        return response
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

# Get company CO2 contribution  
def get_company_co2_contribution(company_id, product_id):

    try:
        company_info = get_company_by_id(company_id)
        company_type = company_info['company_industry']
        
        if company_type == 'farmer':
            product_info = get_products_by_id(product_id)
            quantity = product_info['total_quantity'] if product_info else 0
            emission = farmer_emission(quantity)
        elif company_type == 'processor':
            product_info = get_products_by_id(product_id)
            quantity = product_info['total_quantity'] if product_info else 0
            emission = processor_emission(quantity)
        elif company_type in ['transporter', 'logistics']:
            transport_data = supabase.table('transport')\
                .select('co2_emission')\
                .eq('id_product', product_id)\
                .eq('id_transporter', company_id)\
                .execute()
            
            if transport_data.data:
                emission = sum(t['co2_emission'] for t in transport_data.data)
            else:
                emission = 0
        elif company_type == 'seller':
            seller_product = supabase.table('seller_products')\
                .select('co2_emission')\
                .eq('id_product', product_id)\
                .eq('id_seller', company_id)\
                .execute()
            
            emission = seller_product.data[0]['co2_emission'] if seller_product.data else 0
        else:
            emission = 0
            
        return emission
        
    except Exception as e:
        print(f"Error calculating company CO2 contribution: {e}")
        return 0

# Get sellers with products  
def get_sellers_with_products():

    try:
        seller_products = supabase.table('seller_products') \
            .select('id_seller') \
            .gt('quantity', 0) \
            .execute()
        
        if not seller_products.data:
            return []
        
        seller_ids = set(item['id_seller'] for item in seller_products.data)
        
        sellers = supabase.table('companies') \
            .select('*') \
            .eq('company_industry', 'seller') \
            .eq('status', True) \
            .in_('company_id', list(seller_ids)) \
            .execute()
        
        return sellers.data
        
    except Exception as e:
        print(f"Error getting sellers with products: {e}")
        return []