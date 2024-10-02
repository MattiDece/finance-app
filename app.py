import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
import os

# Funzione per scaricare i ticker dell'S&P 500
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    companies = tables[0][['Symbol', 'Security', 'GICS Sector']]
    return companies

# Funzione per cercare manualmente le aziende
def search_company_manually(queries, sp500_companies):
    tickers = []
    matched_companies = pd.DataFrame()
    
    for query in queries:
        query = query.strip().lower()  
        results = sp500_companies[sp500_companies['Security'].str.lower().str.contains(query)]
        if not results.empty:
            tickers.extend(results['Symbol'].tolist())
            matched_companies = pd.concat([matched_companies, results])
    
    return list(set(tickers)), matched_companies

# Funzione per scaricare i dati finanziari
def get_financial_data(tickers):
    data = {}
    for ticker in tickers:
        stock_data = yf.Ticker(ticker)
        info = stock_data.info
        if all(k in info for k in ['revenueGrowth', 'profitMargins', 'forwardPE', 'beta']):
            historical_data = stock_data.history(period='5y')
            data[ticker] = {
                'historical_data': historical_data,
                'info': info
            }
    return data

# Funzione per calcolare il punteggio di crescita
def calculate_growth_score(data):
    scores = {}
    growth_data = {}
    
    for ticker, info in data.items():
        stock_info = info['info']
        revenue_growth = stock_info['revenueGrowth']
        profit_margin = stock_info['profitMargins']
        pe_ratio = stock_info['forwardPE']
        beta = stock_info['beta']

        # Calcolo del punteggio
        score = (revenue_growth * 0.4 + profit_margin * 0.3 + (1 / pe_ratio) * 0.2 + (1 - beta) * 0.1) * 100
        scores[ticker] = score

        growth_data[ticker] = {
            'Revenue Growth': revenue_growth,
            'Profit Margin': profit_margin,
            'Forward P/E': pe_ratio,
            'Beta': beta,
            'Growth Score': score,
            'Calculation': f'({revenue_growth} * 0.4 + {profit_margin} * 0.3 + (1 / {pe_ratio}) * 0.2 + (1 - {beta}) * 0.1) * 100'
        }
            
    return scores, growth_data

# Funzione per creare grafici interattivi
def plot_interactive_graphs(scores, financial_data):
    # Bar chart interattivo con Plotly
    bar_chart = go.Figure(
        [go.Bar(x=list(scores.keys()), y=list(scores.values()), marker=dict(color='blue'))]
    )
    bar_chart.update_layout(title="Growth Score Comparison", xaxis_title="Companies", yaxis_title="Growth Score")

    # Line chart interattivo con Plotly
    line_chart = go.Figure()
    for ticker, info in financial_data.items():
        historical_data = info['historical_data']
        line_chart.add_trace(go.Scatter(x=historical_data.index, y=historical_data['Close'], mode='lines', name=ticker))

    line_chart.update_layout(title="Historical Price Data", xaxis_title="Date", yaxis_title="Price (USD)")

    return bar_chart, line_chart

# Funzione per la descrizione della strategia
def show_strategy_description():
    return """
    **Strategy Description**:
    
    La nostra strategia si basa su quattro indicatori principali:
    
    1. **Revenue Growth** (40% del punteggio): Indica quanto è cresciuto il fatturato di un'azienda rispetto all'anno precedente.
    2. **Profit Margin** (30% del punteggio): Rappresenta il margine di profitto dell'azienda, cioè la percentuale di guadagno rispetto alle vendite.
    3. **Forward P/E Ratio** (20% del punteggio): Il rapporto prezzo/utili futuro, che indica quanto gli investitori sono disposti a pagare per ogni dollaro di utili previsti.
    4. **Beta** (10% del punteggio): Misura la volatilità dell'azione rispetto al mercato. Un beta inferiore a 1 indica che l'azione è meno volatile del mercato.

    Il punteggio finale è calcolato come:  
    `Punteggio = (Revenue Growth * 0.4 + Profit Margin * 0.3 + (1 / PE) * 0.2 + (1 - Beta) * 0.1) * 100`
    
    **Nota**: Il punteggio massimo che un'azienda può ottenere è **100**.
    
    Questa strategia ci permette di identificare le aziende più promettenti in base a criteri fondamentali. Investire in aziende con solidi fondamentali è essenziale per ottenere risultati sostenibili nel lungo termine.
    """

# Funzione per la guida "How to Use"
def show_how_to_use():
    return """
    **How to Use**:

    1. **Ricerca delle Aziende**: Inserisci i nomi delle aziende che desideri analizzare, separati da virgole (es. 'Apple, Microsoft, Amazon').
    2. **Avvia la Ricerca**: Puoi avviare la ricerca cliccando sul pulsante "Search" oppure premendo il tasto **Invio**.
    3. **Visualizzazione dei Dati**: Dopo la ricerca, vedrai un riepilogo dei dati finanziari delle aziende e i loro punteggi di crescita.
    4. **Grafici Interattivi**: I dati verranno presentati in grafici interattivi, che ti permetteranno di esplorare visivamente le performance storiche delle aziende.
    5. **Dettagli Aggiuntivi**: Puoi consultare la sezione "Strategy Description" per maggiori dettagli sulla metodologia di calcolo dei punteggi.
    """

# Funzione per esportare i dati in Excel
def export_to_excel(data, filepath):
    df = pd.DataFrame(data).T
    df.to_excel(filepath, index=True)
    return filepath

# Interfaccia principale Streamlit
def main():
    st.set_page_config(page_title="Business Analysis S&P 500", layout="wide")

    # Sfondo animato (personalizzazione di stile CSS)
    st.markdown("""
        <style>
            body {
                background-image: url('https://media.giphy.com/media/J2WFHDpGnbZ94/giphy.gif');
                background-size: cover;
            }
            .title {
                font-size: 2.5em;
                color: #ffffff;
                text-align: center;
                margin-top: 50px;
            }
            .container {
                text-align: center;
                color: #ffffff;
            }
        </style>
    """, unsafe_allow_html=True)

    # Titolo
    st.markdown('<h1 class="title">Business Analysis S&P 500</h1>', unsafe_allow_html=True)

    # Elementi decorativi
    st.markdown("""
        <div class="container">
            <h2>Benvenuti nella nostra analisi delle aziende S&P 500!</h2>
            <p>Inserisci i nomi delle aziende nella barra di ricerca e inizia l'analisi.</p>
        </div>
    """, unsafe_allow_html=True)

    # Interfaccia di ricerca
    with st.sidebar:
        st.header("Search Companies")
        user_input = st.text_input("Enter company names (separated by commas)", value="Apple, Microsoft, Amazon")

        # Pulsanti per "How to Use" e "Strategy Description"
        if 'show_how_to_use' not in st.session_state:
            st.session_state.show_how_to_use = False
        if 'show_strategy_description' not in st.session_state:
            st.session_state.show_strategy_description = False

        if st.button("How to Use"):
            st.session_state.show_how_to_use = not st.session_state.show_how_to_use

        if st.button("Strategy Description"):
            st.session_state.show_strategy_description = not st.session_state.show_strategy_description

    # Variabile di stato per la ricerca
    if 'search_triggered' not in st.session_state:
        st.session_state.search_triggered = False

    # Tasto di ricerca
    if st.button("Search") or (user_input and st.session_state.search_triggered):
        # Quando si cerca, chiudere le descrizioni
        st.session_state.show_how_to_use = False
        st.session_state.show_strategy_description = False

        queries = [query.strip() for query in user_input.split(',')]
        sp500_companies = get_sp500_tickers()

        # Cerca le aziende
        tickers, matched_companies = search_company_manually(queries, sp500_companies)

        if tickers:
            financial_data = get_financial_data(tickers)
            scores, growth_data = calculate_growth_score(financial_data)

            # Mostra i risultati in tabella
            st.subheader("Financial Data Results")
            results_df = pd.DataFrame(growth_data).T
            st.dataframe(results_df)

            # Grafici interattivi
            bar_chart, line_chart = plot_interactive_graphs(scores, financial_data)

            # Mostra i grafici
            st.subheader("Growth Score Bar Chart")
            st.plotly_chart(bar_chart)

            st.subheader("Historical Price Data Line Chart")
            st.plotly_chart(line_chart)

            # Pulsante per esportare in Excel
            if st.button("Export to Excel"):
                excel_file_path = "financial_data.xlsx"
                try:
                    filepath = export_to_excel(growth_data, excel_file_path)
                    st.success(f"Data exported successfully to: {os.path.abspath(filepath)}")
                except Exception as e:
                    st.error(f"Error exporting data: {str(e)}")

        st.session_state.search_triggered = True

    # Mostra le informazioni "How to Use" e "Strategy Description"
    if st.session_state.show_how_to_use:
        st.markdown(show_how_to_use())

    if st.session_state.show_strategy_description:
        st.markdown(show_strategy_description())

if __name__ == "__main__":
    main()
