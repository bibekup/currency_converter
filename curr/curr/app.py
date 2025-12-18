import requests
import re
import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta

API_URL = "https://api.freecurrencyapi.com/v1/latest"
HISTORICAL_API_URL = "https://api.freecurrencyapi.com/v1/historical"
API_KEY = "fca_live_ISmw2lF2q42wGHh0lFVnUlBDKRSb1zVezXdRe26S"

#Handles fetching and converting currency data.
class CurrencyConverter:
    def __init__(self):
        self.currencies = {
            "USD": "United States Dollar",
            "EUR": "Euro",
            "AUD": "Australian Dollar",
            "GBP": "British Pound",
            "JPY": "Japanese Yen",
            "INR": "Indian Rupee"
        }
        self.exchange_rates = {}

    #Fetch exchange rates for a given base currency from the API.
    def fetch_exchange_rates(self, base_currency: str):
        try:
            response = requests.get(API_URL, params={"apikey": API_KEY, "base_currency": base_currency})
            response.raise_for_status()
            self.exchange_rates = response.json().get("data", {})
        except requests.RequestException as e:
            st.error(f"Error fetching exchange rates: {e}")
            self.exchange_rates = {}
    #Fetch historical exchange rate for a specific date.
    def fetch_historical_rates(self, base_currency: str, target_currency: str, date: str):
        try:
            response = requests.get(HISTORICAL_API_URL, params={
                "apikey": API_KEY,
                "base_currency": base_currency,
                "currencies": target_currency,
                "date": date
            })
            response.raise_for_status()
            data = response.json().get("data", {})
            if date in data and target_currency in data[date]:
                return data[date][target_currency]
            else:
                return None
        except requests.RequestException as e:
            st.error(f"Error fetching historical rates: {e}")
            return None

    #Generator to fetch historical rates for a range of dates.
    def historical_rate_generator(self, base_currency: str, target_currency: str, start_date: str, end_date: str):
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            rate = self.fetch_historical_rates(base_currency, target_currency, date_str)
            yield {
                "Date": date_str,
                "Rate": rate,
                "Base Currency": base_currency,
                "Target Currency": target_currency
            }
            current_date += timedelta(days=1)
    #Convert an amount to the target currency using fetched exchange rates.
    def convert_currency(self, amount: float, target_currency: str) -> float:
        try:
            rate = self.exchange_rates.get(target_currency)
            if rate is None:
                raise ValueError(f"Currency {target_currency} not supported.")
            return amount * rate
        except ValueError as e:
            st.error(e)
            return 0.0
    #Log conversion details.
    def log_conversion(self, log_type, **kwargs):
        log_entry = f"{log_type} - " + ", ".join([f"{key}: {value}" for key, value in kwargs.items()])
        with open("conversion_log.txt", mode="a") as log_file:
            log_file.write(log_entry + "\n")
#Generate CSV content with headers.
def create_csv(data, headers=None):
    csv = StringIO()
    df = pd.DataFrame(data, columns=headers)
    df.to_csv(csv, index=False)
    return csv.getvalue()
# Validate user input.
def validate_input(input_value, pattern=None, input_type=None):
    if input_type == "numeric":
        try:
            float(input_value)
            if float(input_value) <= 0:
                raise ValueError("Amount must be greater than 0.")
            return True
        except ValueError:
            return False
    elif pattern:
        return bool(re.match(pattern, input_value))
    else:
        return False
#Read conversion logs from the log file.
def read_conversion_logs():
    try:
        with open("conversion_log.txt", "r") as log_file:
            logs = log_file.readlines()
        return logs
    except FileNotFoundError:
        return ["No conversion logs found."]

def main():
    st.set_page_config(page_title="Currency Converter 💱", page_icon="💱", layout="centered")
    st.title("🌍 Currency Converter 💵")
    st.markdown("Convert amounts between various currencies, display historical data, view logs, and download results as a CSV.")

    converter = CurrencyConverter()
    currencies = converter.currencies

    with st.sidebar:
        st.header("Configuration")
        st.caption("Historical data is available starting from January 1, 1999.")
        
        currency_list = list(currencies.keys())
        base_currency = st.selectbox("Select Base Currency", currency_list, index=0)
        target_currency = st.selectbox("Select Target Currency", currency_list, index=1)
        amount = st.number_input("Enter Amount", min_value=0.01, step=0.01, value=1.0)

        # Historical Data Configuration
        st.header("Historical Data")
        start_date = st.date_input(
            "Start Date", 
            value=datetime.now() - timedelta(days=7), 
            min_value=datetime(1999, 1, 1)
        )
        end_date = st.date_input(
            "End Date", 
            value=datetime.now(), 
            min_value=datetime(1999, 1, 1)
        )
        if start_date > end_date:
            st.error("Start Date cannot be later than End Date.")

    if st.button("Convert"):
        # Validate inputs
        if not validate_input(base_currency, r"^[A-Z]{3}$") or not validate_input(target_currency, r"^[A-Z]{3}$"):
            st.error("Invalid currency code. Please use 3-letter codes like 'USD' or 'EUR'.")
            return

        if not validate_input(amount, input_type="numeric"):
            st.error("Invalid amount. Please enter a positive numeric value.")
            return

        converter.fetch_exchange_rates(base_currency)
        if not converter.exchange_rates:
            st.error("No exchange rates available. Check your base currency and API.")
            return

        result = converter.convert_currency(amount, target_currency)
        if result == 0.0:
            st.error("Conversion failed. Please check the currencies and try again.")
            return

        st.success(f"💰 {amount:.2f} {base_currency} = {result:.2f} {target_currency}")
        st.divider()

        # Log the live conversion
        converter.log_conversion("Live Conversion", Base_Currency=base_currency, Target_Currency=target_currency, Amount=amount, Converted_Amount=result, Timestamp=datetime.now())

        # Generate CSV for Conversion
        conversion_data = [{
            "Base Currency": base_currency,
            "Target Currency": target_currency,
            "Amount": amount,
            "Converted Amount": result
        }]
        csv_content = create_csv(conversion_data, headers=["Base Currency", "Target Currency", "Amount", "Converted Amount"])
        st.download_button(label="Download Conversion as CSV", data=csv_content, file_name="conversion.csv", mime="text/csv")

    if st.button("Show Historical Data"):
        st.subheader(f"Historical Exchange Rates: {base_currency} to {target_currency}")
        historical_data = []
        with st.spinner("Fetching historical rates..."):
            for entry in converter.historical_rate_generator(
                base_currency,
                target_currency,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            ):
                historical_data.append(entry)
                # Log the historical data
                converter.log_conversion("Historical Conversion", **entry)

        # Display historical data in a table
        st.table(historical_data)

        # Generate CSV for Historical Data using Lambda Expression
        csv_content = (lambda data: create_csv(data, headers=["Date", "Rate", "Base Currency", "Target Currency"]))(historical_data)
        st.download_button(label="Download Historical Data as CSV", data=csv_content, file_name="historical_data.csv", mime="text/csv")

    if st.button("Show Conversion Logs"):
        st.subheader("Conversion Logs")
        logs = read_conversion_logs()
        for log in logs:
            st.text(log)

if __name__ == "__main__":
    main()
