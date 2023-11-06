import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import plotly.graph_objects as go
import re
import copy
from datetime import datetime
import uuid

app = Flask(__name__, template_folder='templates')

# Define the directory where your data files are located
data_directory = './'

# Define the list of columns to format as percentages
percentage_columns = ['Lovers', 'Bravery', 'Uniquness', 'Quality', 'Value for money', 'Environment friendliness', 'Social responsibility', 'Users']



app.secret_key = 'add your app secret key here'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'

db = SQLAlchemy(app)


class User(db.Model):
    """Model for uploading file"""
    id = db.Column(db.String(120), nullable=False, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    updated_at = db.Column(db.String(120), nullable=False, default=datetime.utcnow())
    password= db.Column(db.String(200), nullable=False, unique=False)
    full_name = db.Column(db.String(200), nullable=False, unique=False)


with app.app_context():   # all database operations under with
    db.create_all() 


@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        account = User.query.filter_by(email=email).first()
        if (account == None or account.password != password):
            flash('Incorrect username / password !')
            return redirect(url_for('login'))
        
        else:
            session['loggedin'] = True
            session['id'] = account.id
            session['email'] = account.email
            flash('login Successfully !')
            return redirect(url_for('index'))

    return render_template('login.html', msg = msg)



@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('email', None)
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')
        email = request.form.get('email')
        confirm_password = request.form.get('confirm_password')

        account = User.query.filter_by(email=email).first()
        if account:
            msg = 'Account already Exits !'
        elif password != confirm_password:
            msg = 'Password and confirm_password most be same !'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address !'
        elif not name or not password or not email:
            msg = 'Please fill out the form !'
        else:
            user = User(email=email, password=password, full_name= name, id=str(uuid.uuid4()))
            db.session.add(user)
            db.session.commit()
            msg = 'Register successfully'
            flash(msg)
            return redirect(url_for('login'))

        flash(msg)
        return redirect(url_for('register'))

    return render_template('register.html', msg=msg)



def country_year(brand, category):
    file = './sheet/BrandPresentFrom.xlsx'
    country_json = {}
    year_data = pd.read_excel(file)

    igaunija_list = ['Igaunija', 'Lietuva', 'Latvija', 'Baltija']
    igaunija_list_abb = {'Igaunija':'EE', 'Lietuva': 'LT', 'Latvija': 'LV', 'Baltija':'BAL'}

    for ig in igaunija_list:
        first_occurrence_index = year_data.columns.get_loc(ig)

        data_subset = year_data.iloc[:, first_occurrence_index:first_occurrence_index + 11]
        if ig == 'Igaunija' or ig == 'Lietuva':
            data_subset = year_data.iloc[:, first_occurrence_index:first_occurrence_index + 8]

        first_two_columns = year_data.iloc[:, :2]
        concatenated_data = pd.concat([first_two_columns, data_subset], axis=1)

        concatenated_data.columns = concatenated_data.iloc[0]

        concatenated_data = concatenated_data.drop(concatenated_data.index[0])

        # Reset the index to start from 0
        concatenated_data = concatenated_data.reset_index(drop=True)

        filtered_data = concatenated_data[concatenated_data['Brand'] == brand]
        
        filtered_data = filtered_data[filtered_data['Category'] == category]

        last_non_nan_column = None

        for column in filtered_data.columns[3:]:
            last_non_nan_value = filtered_data[column].last_valid_index()
            if last_non_nan_value is not None:
                last_non_nan_column = column

        # Check if there is a last non-NaN column
        if last_non_nan_column is not None:
            country_json[igaunija_list_abb[ig]] = int(last_non_nan_column)
        else:
            country_json[igaunija_list_abb[ig]] = last_non_nan_column
    return country_json   

@app.route('/')
def index():
    id = session.get('id')
    if (id == None or User.query.filter_by(id=id).first() == None):
        return redirect(url_for('login'))
    all_brand_names = []
    excel_files = ['./DataSet_2022_test.xlsx', './DataSet_2023_test.xlsx','./DataSet_2021_test.xlsx']
    for file in excel_files:
        df = pd.read_excel(file, engine='openpyxl')

        brand_names = df['Brand_name'].tolist()

        all_brand_names.extend(brand_names)

    brands_name = []
    for i in all_brand_names:
        if i not in brands_name:
            brands_name.append(i)
    return render_template('index.html',brand_names=brands_name)

@app.route('/search', methods=['POST'])
def search():
    id = session.get('id')
    if (id == None or User.query.filter_by(id=id).first() == None):
        return redirect(url_for('login'))
    
    brand_name = request.form.get('brand_name')
    brand_info_list = []  # List to store results for multiple years

    default = {'baltic_2021': [], 'country_lt_2021': [], 'country_lv_2021': [], 'country_ee_2021': [], 
                'baltic_2022': [], 'country_lt_2022': [], 'country_lv_2022': [], 'country_ee_2022': [], "country_year": {},
                'baltic_2023': [], 'country_lt_2023': [], 'country_lv_2023': [], 'country_ee_2023': [], "years": {"2023": False, "2022": False, "2021": False}}
    category_names = {}
    show_brand = ""

    for year_file in os.listdir(data_directory):

        if year_file.endswith('.xlsx'):
            year = year_file.split('_')[-1].split('.')[0]  # Extract the year from the filename

            # Read data from the current year's Excel file
            year_data = pd.read_excel(os.path.join(data_directory, year_file), sheet_name='Data')
          
            brand_info = year_data[year_data['Brand_name'].str.lower().eq(brand_name.lower())]

            # Convert the specified columns to numeric
            for column in percentage_columns:
                if column in brand_info:
                    brand_info[column] = pd.to_numeric(brand_info[column], errors='coerce')


            brand_info_dict = brand_info.to_dict(orient='records')
            if brand_info_dict != []:
                show_brand = brand_info_dict[0]['Brand_name']
           
            for record in brand_info_dict:
                for column in percentage_columns:
                    if column in record:
                        if pd.notna(record[column]):  # Check for NaN values
                            record[column] = f'{record[column]:.2%}'
                        else:
                            record[column] = ''  # Replace NaN with an empty string

            brand_info_list.append({'year': year, 'data': brand_info_dict})

            country_2023 = ['Lovers','Bravery','Quality','Value for money','Environment friendliness','Social responsibility','Users']
            countries = ['Lovers','Uniquness','Quality','Value for money','Environment friendliness','Social responsibility','Users']
            country = ['Lovers','Uniquness','Quality','Value for money','Environment friendliness','Social responsibility']

            if brand_info_dict != []:
                if brand_info_dict[0]['Year'] == 2023:
                    for i in range(len(brand_info_dict)):
                        if category_names.get(brand_info_dict[i]['Category']) == None:
                            default['country_year'] = country_year(brand_name, brand_info_dict[i]['Category'])
                            category_names[brand_info_dict[i]['Category']] = copy.deepcopy(default)

                        category_names[brand_info_dict[i]['Category']]['years']["2023"] = True

                        if brand_info_dict[i]['Country'] == 'EE':
                            for j in country_2023:
                                category_names[brand_info_dict[i]['Category']]['country_ee_2023'].append(brand_info_dict[i][j])
        
                        if brand_info_dict[i]['Country'] == 'LV':
                            for j in country_2023:
                                category_names[brand_info_dict[i]['Category']]['country_lv_2023'].append(brand_info_dict[i][j])

                        if brand_info_dict[i]['Country'] == 'LT':
                            for j in country_2023:
                                category_names[brand_info_dict[i]['Category']]['country_lt_2023'].append(brand_info_dict[i][j])

                        if brand_info_dict[i]['Country'] == 'BALTIC':
                            for j in country_2023:
                                category_names[brand_info_dict[i]['Category']]['baltic_2023'].append(brand_info_dict[i][j])

                if brand_info_dict[0]['Year'] == 2022:
                    for i in range(len(brand_info_dict)):
                        if category_names.get(brand_info_dict[i]['Category']) == None:
                            category_names[brand_info_dict[i]['Category']] = copy.deepcopy(default)
                            
                        category_names[brand_info_dict[i]['Category']]['years']["2022"] = True
                        if brand_info_dict[i]['Country'] == 'EE':
                            for j in countries:
                                category_names[brand_info_dict[i]['Category']]['country_ee_2022'].append(brand_info_dict[i][j])

                        if brand_info_dict[i]['Country'] == 'LV':
                            for j in countries:
                                category_names[brand_info_dict[i]['Category']]['country_lv_2022'].append(brand_info_dict[i][j])

                        if brand_info_dict[i]['Country'] == 'LT':
                            for j in countries:
                                category_names[brand_info_dict[i]['Category']]['country_lt_2022'].append(brand_info_dict[i][j])

                        if brand_info_dict[i]['Country'] == 'BALTIC':
                            for j in countries:
                                category_names[brand_info_dict[i]['Category']]['baltic_2022'].append(brand_info_dict[i][j])

                if brand_info_dict[0]['Year'] == 2021:
                    for i in range(len(brand_info_dict)):
                        if category_names.get(brand_info_dict[i]['Category']) == None:
                            category_names[brand_info_dict[i]['Category']] = copy.deepcopy(default)
                        category_names[brand_info_dict[i]['Category']]['years']["2021"] = True

                        if brand_info_dict[i]['Country'] == 'EE':
                            for j in country:
                                category_names[brand_info_dict[i]['Category']]['country_ee_2021'].append(brand_info_dict[i][j])

                        if brand_info_dict[i]['Country'] == 'LV':
                            for j in country:
                                category_names[brand_info_dict[i]['Category']]['country_lv_2021'].append(brand_info_dict[i][j])

                        if brand_info_dict[i]['Country'] == 'LT':
                            for j in countries:
                                if (brand_info_dict[i].get(j)):
                                    category_names[brand_info_dict[i]['Category']]['country_lt_2021'].append(brand_info_dict[i][j])

                        if brand_info_dict[i]['Country'] == 'BALTIC':
                            for j in country:
                                category_names[brand_info_dict[i]['Category']]['baltic_2021'].append(brand_info_dict[i][j])
    data = {'EE': 2015.0, 'LT': 2015.0, 'LV': 2012.0, 'BAL': 2012.0}
    return render_template('main.html', category_names = category_names, brand_info_list=brand_info_list, brand_name= show_brand, country_data=data)



if __name__ == '__main__':
    app.run()
