from flask import Flask, request, render_template, send_file, jsonify
import requests
import pandas as pd
import io
import os
from pathlib import Path
from flask_socketio import SocketIO, emit
from tableauhyperapi import HyperProcess, Connection, Telemetry, TableDefinition, SqlType, Inserter, TableName, CreateMode
from tableauserverclient import TableauAuth, Server, Pager, DatasourceItem


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = "uploads"
HYPER_FOLDER = "hyper_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(HYPER_FOLDER, exist_ok=True)

# Add CSP headers to avoid security issues
@app.after_request
def add_csp_headers(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self';"
    )
    return response

@app.route("/")
def home():
    return render_template("index.html")



@app.route("/get_xlsx", methods=["POST"])
def get_xlsx():
    try:
        # Get API details from the form
        api_url = request.form.get("api_url")
        app_id = request.form.get("app_id")

        if not api_url or not app_id:
            return jsonify({"error": "API URL and Application ID are required."}), 400

        # Replace appId in the URL if needed
        if "appId=" in api_url:
            api_url = api_url.replace("appId=", f"appId={app_id}")

        # Extract statsDataId for naming the output file
        try:
            stats_data_id = api_url.split("statsDataId=")[1].split("&")[0]
        except IndexError:
            stats_data_id = "processed_data"

        # Initialize pagination variables
        start_position = 1
        limit = 10000
        total_records_fetched = 0
        combined_data = []

        while True:
            # Update the API URL with pagination parameters
            params = {
                "appId": app_id,
                "lang": "E",
                "statsDataId": stats_data_id,
                "metaGetFlg": "Y",
                "cntGetFlg": "N",
                "explanationGetFlg": "Y",
                "annotationGetFlg": "Y",
                "sectionHeaderFlg": "1",
                "replaceSpChars": "0",
                "startPosition": start_position,
                "limit": limit
            }

            # Make a GET request to the API
            response = requests.get(api_url, params=params)
            response.raise_for_status()

            # Decode the response content and split into lines
            content = response.content.decode("utf-8").splitlines()

            # If content is empty, break the loop
            if not content:
                break

            # Append the data to the combined data list
            combined_data.extend(content)

            # Count fetched records
            fetched_records = len(content)
            total_records_fetched += fetched_records

            # Send progress update to the frontend
            socketio.emit("progress", {"records_fetched": total_records_fetched})

            # Check if fewer records than the limit were returned
            if fetched_records < limit:
                break

            # Update startPosition for the next batch
            start_position += limit

        # Convert the combined data to a DataFrame
        csv_data = "\n".join(combined_data)
        df = pd.read_csv(io.StringIO(csv_data))

        # Save to Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")

        output.seek(0)
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{stats_data_id}.xlsx"
        )

    except requests.exceptions.RequestException as e:
        socketio.emit("error", {"message": str(e)})
        return jsonify({"error": f"API request failed: {e}"}), 500

    except Exception as e:
        socketio.emit("error", {"message": str(e)})
        return jsonify({"error": str(e)}), 500


def convert_excel_to_hyper(excel_file, hyper_file, table_name="Extract"):
    try:
        # Ensure the output folder exists
        hyper_path = Path(hyper_file)
        hyper_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing .hyper file if it exists
        if hyper_path.exists():
            os.remove(hyper_path)
            print(f"Removed existing Hyper file: {hyper_file}")

        # Load Excel data
        print(f"Loading Excel file: {excel_file}")
        df = pd.read_excel(excel_file)
        if df.empty:
            raise ValueError("Excel file is empty")

        # Replace NaN values with empty strings
        df = df.fillna('')

        # Print DataFrame structure for debugging
        print("DataFrame columns and types:")
        print(df.dtypes)

        # Dynamically define column types for the Hyper table
        column_types = {
            col: SqlType.text() if df[col].dtype == 'object' else SqlType.double()
            for col in df.columns
        }

        # Debug: Print detected column types
        print("Detected Column Types:")
        for col, col_type in column_types.items():
            print(f"Column: {col}, Type: {col_type}")

        # Create the Hyper file
        with HyperProcess(telemetry=Telemetry.SEND_USAGE_DATA_TO_TABLEAU) as hyper:
            print("Hyper process initialized.")
            with Connection(endpoint=hyper.endpoint, database=str(hyper_path), create_mode=CreateMode.CREATE_AND_REPLACE) as connection:
                # Define the table schema dynamically based on the DataFrame columns
                table_definition = TableDefinition(
                    table_name=TableName("public", table_name),
                    columns=[
                        TableDefinition.Column(col, column_types[col]) 
                        for col in df.columns
                    ]
                )
                # Create the table in the Hyper file
                connection.catalog.create_table(table_definition)

                # Insert data into the Hyper table
                with Inserter(connection, table_definition) as inserter:
                    inserter.add_rows(df.to_numpy())
                    inserter.execute()

                print(f"Hyper file created at {hyper_file}")

        # If everything succeeded
        return True

    except Exception as e:
        print(f"Error during Hyper file creation: {e}")
        import traceback
        traceback.print_exc()
        return False




# def publish_hyper_to_tableau(tableau_server, username, password, project_name, hyper_file):
#     if not os.path.exists(hyper_file):
#         raise FileNotFoundError(f"Hyper file does not exist at {hyper_file}")

#     tableau_auth = TableauAuth(username, password)
#     server = Server(tableau_server, use_server_version=True)
#     try:
#         with server.auth.sign_in(tableau_auth):
#             # Find the project by name
#             project = next((proj for proj in Pager(server.projects) if proj.name == project_name), None)
#             if not project:
#                 raise ValueError(f"Project '{project_name}' not found on Tableau Server")

#             # Publish the Hyper file as a data source
#             datasource = DatasourceItem(project_id=project.id)
#             datasource = server.datasources.publish(datasource, hyper_file, mode="Overwrite")
#             print(f"Published {hyper_file} to Tableau in project '{project_name}'")
#     except Exception as e:
#         raise Exception(f"Failed to publish to Tableau: {e}")


# @app.route("/xlsx_to_tableau", methods=["POST"])
# def xlsx_to_tableau():
#     try:
#         uploaded_file = request.files.get("xlsx_file")
#         tableau_server = request.form.get("tableau_server_url")
#         username = request.form.get("tableau_username")
#         password = request.form.get("tableau_password")
#         project_name = request.form.get("tableau_project_name")

#         if not uploaded_file or not tableau_server or not username or not password or not project_name:
#             return jsonify({"error": "Missing required parameters"}), 400

#         excel_file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
#         uploaded_file.save(excel_file_path)

#         hyper_file_path = os.path.join(HYPER_FOLDER, Path(uploaded_file.filename).stem + ".hyper")
#         print(f"Excel file saved to: {excel_file_path}")
#         print(f"Hyper file path: {hyper_file_path}")

#         if not convert_excel_to_hyper(excel_file_path, hyper_file_path):
#             return jsonify({"error": "Failed to convert Excel to Hyper file"}), 500

#         # Publish to Tableau with all required arguments
#         publish_hyper_to_tableau(tableau_server, username, password, project_name, hyper_file_path)
#         return jsonify({"message": f"Successfully published {hyper_file_path} to Tableau"}), 200
#     except Exception as e:
#         print(f"Error: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

def publish_hyper_to_tableau(tableau_server, username, password, site_id, project_name, hyper_file):
    if not os.path.exists(hyper_file):
        raise FileNotFoundError(f"Hyper file does not exist at {hyper_file}")

    # Include the site_id in TableauAuth
    tableau_auth = TableauAuth(username, password, site_id)
    server = Server(tableau_server, use_server_version=True)
    
    try:
        with server.auth.sign_in(tableau_auth):
            print(f"Signed in to Tableau Server: {tableau_server}")

            # Find the project by name
            project = next((proj for proj in Pager(server.projects) if proj.name == project_name), None)
            if not project:
                raise ValueError(f"Project '{project_name}' not found on Tableau Server")

            # Publish the Hyper file as a data source
            datasource = DatasourceItem(project_id=project.id)
            datasource = server.datasources.publish(datasource, hyper_file, mode="Overwrite")
            print(f"Published {hyper_file} to Tableau in project '{project_name}'")
    except Exception as e:
        raise Exception(f"Failed to publish to Tableau: {e}")


@app.route("/xlsx_to_tableau", methods=["POST"])
def xlsx_to_tableau():
    try:
        uploaded_file = request.files.get("xlsx_file")
        tableau_server = request.form.get("tableau_server_url")
        username = request.form.get("tableau_username")
        password = request.form.get("tableau_password")
        site_id = request.form.get("tableau_site_id")  # Add site_id field
        project_name = request.form.get("tableau_project_name")

        if not uploaded_file or not tableau_server or not username or not password or not project_name or not site_id:
            return jsonify({"error": "Missing required parameters"}), 400

        excel_file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(excel_file_path)

        hyper_file_path = os.path.join(HYPER_FOLDER, Path(uploaded_file.filename).stem + ".hyper")
        print(f"Excel file saved to: {excel_file_path}")
        print(f"Hyper file path: {hyper_file_path}")

        if not convert_excel_to_hyper(excel_file_path, hyper_file_path):
            return jsonify({"error": "Failed to convert Excel to Hyper file"}), 500

        # Publish to Tableau with all required arguments
        publish_hyper_to_tableau(tableau_server, username, password, site_id, project_name, hyper_file_path)
        return jsonify({"message": f"Successfully published {hyper_file_path} to Tableau"}), 200
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)