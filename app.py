import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from alpha_vantage.fundamentaldata import FundamentalData
import io

# Replace 'your_api_key' with your actual Alpha Vantage API key
ALPHA_VANTAGE_API_KEY = 'your_api_key'
alpha_vantage_fd = FundamentalData(ALPHA_VANTAGE_API_KEY)

# Funzione per esportare i dati in un file Excel e permettere il download
def export_data_to_excel(data):
    output = io.BytesIO()  # Crea un buffer in memoria per salvare il file Excel
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:  # Usa un contesto di gestione per scrivere su Excel
        df = pd.DataFrame(data).T  # Trasforma i dati in un DataFrame
        df.to_excel(writer, index=True, sheet_name='Financial Data')  # Scrivi i dati nel foglio Excel
    processed_data = output.getvalue()  # Ottieni i dati processati
    return processed_data

# Funzione per scaricare i ticker dell'S&P 500
@st.cache_data
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    companies = tables[0][['Symbol', 'Security', 'GICS Sector']]
    return companies

# Funzione per cercare manualmente le aziende
def search_company_manually(queries, sp500_companies):
    tickers = []
    matched_companies = pd.DataFrame()
    not_found_tickers = []

# Normalizza le query separando le parole
    for query in queries:
        query = query.strip().lower()
        # Separa le parole nella query
        query_words = query.split()

    # Crea una maschera che verifica se tutte le parole sono presenti nel nome della società
        mask = sp500_companies['Security'].str.lower().str.contains(query_words[0])
        for word in query_words[1:]:
            mask &= sp500_companies['Security'].str.lower().str.contains(word)
        
        results = sp500_companies[mask]
        
        if not results.empty:
            tickers.extend(results['Symbol'].tolist())
            matched_companies = pd.concat([matched_companies, results])
        else:
            not_found_tickers.append(query)  # Aggiungi tickers non trovati

    return list(set(tickers)), matched_companies, not_found_tickers

# Funzione per scaricare i dati finanziari
def get_financial_data(tickers):
    data = {}
    for ticker in tickers:
        stock_data = yf.Ticker(ticker)
        info = stock_data.info
        
        # Check if required data is missing, if so use Alpha Vantage
        if all(k in info for k in ['revenueGrowth', 'profitMargins', 'forwardPE', 'beta', 'returnOnEquity', 'debtToEquity', 'freeCashflow', 'dividendYield']):
            historical_data = stock_data.history(period='5y')
            data[ticker] = {
                'historical_data': historical_data,
                'info': info
            }
        else:
            # Fallback to Alpha Vantage
            try:
                av_data, _ = alpha_vantage_fd.get_company_overview(ticker)
                info = {**info, **av_data}  # Merge data from Alpha Vantage
                historical_data = stock_data.history(period='5y')  # Still using yfinance for historical data
                data[ticker] = {
                    'historical_data': historical_data,
                    'info': info
                }
            except Exception as e:
                st.warning(f"Could not retrieve data for {ticker} from both Yahoo Finance and Alpha Vantage: {str(e)}")

    return data

# Funzione per calcolare il punteggio di crescita con le nuove metriche
def calculate_growth_score(data):
    scores = {}
    growth_data = {}

    for ticker, info in data.items():
        stock_info = info['info']

        # Normalizzazione e raccolta delle metriche
        revenue_growth = stock_info.get('revenueGrowth', 0)
        profit_margin = stock_info.get('profitMargins', 0)
        pe_ratio = stock_info.get('forwardPE', 1)  # avoid division by 0
        beta = stock_info.get('beta', 1)
        roe = stock_info.get('returnOnEquity', 0)
        debt_to_equity = stock_info.get('debtToEquity', 0)
        free_cash_flow = stock_info.get('freeCashflow', 0) / 1e9  # Scale to billions
        dividend_yield = stock_info.get('dividendYield', 0)

        # Normalizzazione delle metriche (su scala 0-1)
        revenue_growth_norm = (revenue_growth + 1) / 2  # assume -100% < crescita < 100%
        profit_margin_norm = (profit_margin + 1) / 2  # assume -100% < margine < 100%
        pe_ratio_norm = min(1, 1 / pe_ratio)  # 1/P/E, normalizzato a massimo 1
        beta_norm = 1 - min(beta, 1)  # meno beta è meglio, normalizzato a massimo 1
        roe_norm = roe / 50  # ROE scalato su 50% massimo
        debt_to_equity_norm = 1 - min(debt_to_equity / 2, 1)  # meno debito è meglio, massimo 2x equity
        free_cash_flow_norm = min(free_cash_flow / 10, 1)  # Scalato a un massimo di 10 miliardi
        dividend_yield_norm = min(dividend_yield / 0.1, 1)  # Dividend Yield, massimo 10%

        # Calcolo del punteggio ponderato
        score = (
            revenue_growth_norm * 0.25 +  # 25% del peso totale
            profit_margin_norm * 0.15 +   # 15% del peso totale
            pe_ratio_norm * 0.15 +        # 15% del peso totale
            beta_norm * 0.05 +            # 5% del peso totale
            roe_norm * 0.15 +             # 15% del peso totale
            debt_to_equity_norm * 0.10 +  # 10% del peso totale
            free_cash_flow_norm * 0.10 +  # 10% del peso totale
            dividend_yield_norm * 0.05    # 5% del peso totale
        ) * 100

        scores[ticker] = score

        growth_data[ticker] = {
            'Revenue Growth': revenue_growth,
            'Profit Margin': profit_margin,
            'Forward P/E': pe_ratio,
            'Beta': beta,
            'ROE': roe,
            'Debt-to-Equity': debt_to_equity,
            'Free Cash Flow (Billion $)': free_cash_flow,
            'Dividend Yield': dividend_yield,
            'Growth Score': score,
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

    line_chart.update_layout(title="Historical Price Data", xaxis_title="Date", yaxis_title="Price (USD)", height=600)  # Aumentata l'altezza

    return bar_chart, line_chart

# Funzione per la descrizione della strategia
def show_strategy_description():
    return """
    **Strategy Description**:

    La nostra strategia di analisi aziendale si basa su otto indicatori chiave che ci permettono di valutare la crescita e la stabilità delle aziende. Questi indicatori sono scelti per fornire un quadro complessivo delle performance finanziarie e operazionali di ogni azienda. Di seguito, una descrizione dettagliata di ciascuna metrica utilizzata nel calcolo del punteggio:

    1. **Revenue Growth (25%)**: Misura la crescita delle entrate nel tempo. Un'azienda con una crescita costante delle entrate è generalmente considerata più solida e promettente. La crescita può derivare da un aumento delle vendite, dall'acquisizione di nuovi clienti o dall'espansione in nuovi mercati. Le aziende che mostrano una crescita sostenuta delle entrate sono spesso più attraenti per gli investitori.

    2. **Profit Margin (15%)**: Rappresenta la redditività operativa dell'azienda. Un margine di profitto elevato indica che l'azienda è in grado di gestire bene i costi e generare profitti dai suoi ricavi. Questo indicatore è cruciale per capire quanto l'azienda riesca a mantenere del suo fatturato dopo aver coperto le spese operative. Margini più alti possono anche suggerire un vantaggio competitivo o una gestione efficiente.

    3. **Forward P/E Ratio (15%)**: Questa metrica confronta il prezzo delle azioni con gli utili previsti. Un rapporto P/E inferiore indica che le azioni potrebbero essere sottovalutate rispetto ai guadagni futuri. Gli investitori utilizzano questo indicatore per valutare se un'azione è un buon affare rispetto ad altre opzioni di investimento.

    4. **Beta (5%)**: Misura la volatilità di un'azione rispetto al mercato. Un beta superiore a 1 indica che l'azione è più volatile rispetto al mercato, mentre un beta inferiore a 1 indica meno volatilità. Gli investitori usano questo indicatore per valutare il rischio associato a un'azione e per costruire un portafoglio equilibrato.

    5. **Return on Equity (ROE) (15%)**: Misura la redditività in relazione al capitale proprio degli azionisti. Un ROE elevato indica che l'azienda sta generando un buon ritorno sugli investimenti dei suoi azionisti, il che è un segnale positivo per gli investitori.

    6. **Debt-to-Equity Ratio (10%)**: Indica il livello di indebitamento di un'azienda rispetto al capitale proprio. Un rapporto inferiore suggerisce una minore dipendenza dal debito, il che è visto favorevolmente dagli investitori. Le aziende con elevati livelli di debito possono affrontare rischi maggiori, specialmente in periodi di recessione.

    7. **Free Cash Flow (10%)**: Rappresenta il flusso di cassa disponibile per gli azionisti dopo che l'azienda ha coperto le spese di capitale. Un flusso di cassa libero positivo è un segnale forte che l'azienda ha risorse disponibili per investimenti, pagamenti di dividendi o per ridurre il debito.

    8. **Dividend Yield (5%)**: Indica la rendita da dividendi rispetto al prezzo delle azioni. Un alto dividend yield può essere attraente per gli investitori in cerca di flussi di reddito. Tuttavia, è importante considerare la sostenibilità di tali dividendi in relazione alla salute finanziaria complessiva dell'azienda.

    La somma ponderata di queste metriche ci fornisce un punteggio di crescita che possiamo utilizzare per confrontare diverse aziende e prendere decisioni informate sugli investimenti. Questo approccio ci consente di considerare non solo i risultati finanziari attuali, ma anche le prospettive future e il rischio associato a ciascuna azienda.
    """

# Funzione per la descrizione su come utilizzare il programma
def show_how_to_use():
    return """
    **How to Use the Program**:

    1. **Input Company Name or Ticker**: Inserisci il nome o il ticker dell'azienda che desideri analizzare. Puoi inserire più aziende separandole con una virgola.

    2. **Search**: Clicca sul pulsante "Search" o premi il tasto "Invio" sulla tastiera per avviare la ricerca. Il programma cercherà le aziende corrispondenti all'inserimento.

    3. **Matched Companies**: Dopo la ricerca, vedrai un elenco delle aziende corrispondenti insieme ai loro ticker. Se non viene trovata alcuna azienda, verrà visualizzato un messaggio di avviso.

    4. **Growth Scores**: Sarai in grado di vedere i punteggi di crescita calcolati per le aziende selezionate. Questi punteggi sono basati su vari indicatori finanziari.

    5. **Financial Data Table**: Una tabella dettagliata mostrerà i dati finanziari chiave per ciascuna azienda.

    6. **Historical Price Data**: Potrai visualizzare i dati storici sui prezzi delle azioni nel tempo attraverso un grafico interattivo.

    7. **Growth Score Comparison**: Con il grafico a barre, potrai confrontare visivamente i punteggi di crescita delle diverse aziende.

    8. **How to Use / Strategy Description**: Usa i pulsanti "How to Use" e "Strategy Description" per ottenere ulteriori informazioni su come utilizzare il programma e sulla strategia di analisi utilizzata.
    """

# Impostazioni della pagina
st.set_page_config(layout="wide")  # Imposta il layout su "wide"

# Interfaccia dell'applicazione Streamlit
st.title("S&P500 Stock Analysis")
sp500_companies = get_sp500_tickers()
query = st.text_input("Enter Company Name or Ticker:", "", key='company_input', placeholder="Type here...")

# Variabili di stato per controllare i testi dei pulsanti
show_how_to_use_text = st.session_state.get('show_how_to_use_text', False)
show_strategy_description_text = st.session_state.get('show_strategy_description_text', False)

# Creazione delle colonne per i pulsanti
col1, col2, col3 = st.columns([2, 2, 2])  # Crea 3 colonne di dimensione uguale
with col1:
    search_button = st.button("Search")
with col2:
    how_to_use_button = st.button("How to Use", on_click=lambda: st.session_state.update({'show_how_to_use_text': not show_how_to_use_text}))
with col3:
    strategy_description_button = st.button("Strategy Description", on_click=lambda: st.session_state.update({'show_strategy_description_text': not show_strategy_description_text}))

if search_button or (query and st.session_state.get('last_query') != query):
    st.session_state['last_query'] = query
    if query:
        tickers, matched_companies, not_found_tickers = search_company_manually(query.split(','), sp500_companies)
        
        # Mostra messaggi di errore per le aziende non trovate
        if not_found_tickers:
            for ticker in not_found_tickers:
                st.error(f"No matching company found for '{ticker}'. Please check the name or ticker.")

        if matched_companies.empty:
            st.error("No matching companies found for the provided tickers.")
        else:
            financial_data = get_financial_data(tickers)
            scores, growth_data = calculate_growth_score(financial_data)

            # Display the results
        
        # Sezione divisa in due colonne: "Matched Companies" e "Growth Scores"
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Matched Companies:")
                st.dataframe(matched_companies)

            with col2:
               st.subheader("Growth Scores:")
               for company, score in scores.items():
                     st.markdown(f"{company}: <span style='color:yellow; font-weight:bold;'>{score:.2f}</span>", unsafe_allow_html=True)


            st.subheader("Financial Data Table:")
            financial_df = pd.DataFrame.from_dict(growth_data, orient='index')
            st.dataframe(financial_df.style.set_table_attributes("style='height: 800px; width: 100%;'"))  # Aumenta ulteriormente le dimensioni della tabella
            
            # Aggiungi questo blocco subito dopo la visualizzazione dei dati finanziari
            excel_data = export_data_to_excel(growth_data)  # Usa i dati finanziari da esportare
            st.download_button(
                    label="Export to Excel",
                    data=excel_data,
                    file_name='financial_data.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )

            st.subheader("Historical Price Data:")
            bar_chart, line_chart = plot_interactive_graphs(scores, financial_data)
            st.plotly_chart(line_chart)

            st.subheader("Growth Score Comparison:")
            st.plotly_chart(bar_chart)

    else:
        st.warning("Please enter a company name or ticker.")

# Mostra le descrizioni in base ai pulsanti
if show_how_to_use_text:
    st.subheader("How to Use:")
    st.write(show_how_to_use())

if show_strategy_description_text:
    st.subheader("Strategy Description:")
    st.write(show_strategy_description())

