import streamlit as st
import numpy as np
import pandas as pd
import altair as alt

# Funktion för att simulera Brownsk rörelse (GBM)


def simulate_gbm(S0, mu, sigma, T, dt):
    N = int(T / dt)
    t = np.linspace(0, T, N)
    W = np.random.standard_normal(size=N)
    W = np.cumsum(W) * np.sqrt(dt)
    X = (mu - 0.5 * sigma**2) * t + sigma * W
    S = S0 * np.exp(X)
    # Begränsa priserna mellan 100 och 300
    S = np.clip(S, 100, 300)
    return t, S

# Funktion för att generera en orderbok


def generate_order_book(current_price, n_orders=5):
    # Generera köppriser nära aktuellt pris
    buy_prices = np.round(np.sort(np.random.uniform(
        0.98, 1.00, n_orders) * current_price)[::-1], 2)
    # Generera säljpriser nära aktuellt pris
    sell_prices = np.round(np.sort(np.random.uniform(
        1.00, 1.02, n_orders) * current_price), 2)
    buy_orders = np.random.randint(10, 100, n_orders)
    sell_orders = np.random.randint(10, 100, n_orders)
    order_book = pd.DataFrame({
        "Köp-pris": buy_prices,
        "Köp-volym": buy_orders,
        "Sälj-pris": sell_prices,
        "Sälj-volym": sell_orders,
    })
    return order_book

# Funktion för att hantera köp


def handle_buy(order_book, portfolio, balance, stock_name, price, volume):
    # Hitta alla säljorder med pris <= användarens pris
    matching_orders = order_book[order_book["Sälj-pris"] <= price]
    if not matching_orders.empty:
        # Sortera matchande order efter pris (lägsta först)
        matching_orders = matching_orders.sort_values(by="Sälj-pris")
        total_volume_needed = volume
        total_cost = 0
        purchased_volume = 0
        for idx, order in matching_orders.iterrows():
            available_volume = order["Sälj-volym"]
            sell_price = order["Sälj-pris"]
            trade_volume = min(available_volume, total_volume_needed)
            trade_cost = trade_volume * sell_price
            if balance >= trade_cost:
                balance -= trade_cost
                total_cost += trade_cost
                purchased_volume += trade_volume
                total_volume_needed -= trade_volume
                # Uppdatera eller ta bort ordern från orderboken
                if available_volume > trade_volume:
                    order_book.at[idx, "Sälj-volym"] -= trade_volume
                else:
                    order_book = order_book.drop(idx)
                if total_volume_needed == 0:
                    break
            else:
                st.error("Du har inte tillräckligt med pengar!")
                break
        if purchased_volume > 0:
            portfolio[stock_name] = portfolio.get(
                stock_name, 0) + purchased_volume
            st.success(f"Köpt {purchased_volume} aktier av {
                       stock_name} för totalt {total_cost:.2f} SEK")
            return True, balance, portfolio, order_book
        else:
            st.error("Kunde inte köpa aktier. Kontrollera ditt saldo.")
    else:
        st.error("Det finns inga säljorder till det priset eller lägre.")
    return False, balance, portfolio, order_book


# Titel
st.title("Aktiesimulator 📈")
st.write("Lär dig att handla aktier i en simulerad miljö.")

# Slumpa startkapital och ISK konto
if "balance" not in st.session_state:
    st.session_state["balance"] = 100_000  # Fixed starting balance
if "isk_konto" not in st.session_state:
    st.session_state["isk_konto"] = f"ISK-{np.random.randint(1000, 9999)}"
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = {}
if "order_book" not in st.session_state:
    st.session_state["order_book"] = None  # Will be generated later
if "latest_prices" not in st.session_state:
    st.session_state["latest_prices"] = {}

balance = st.session_state["balance"]
isk_konto = st.session_state["isk_konto"]
portfolio = st.session_state["portfolio"]
latest_prices = st.session_state["latest_prices"]

st.sidebar.subheader("ISK Konto")
st.sidebar.write(f"**Konto-ID:** {isk_konto}")
st.sidebar.write(f"**Saldo:** {balance:.2f} SEK")

# Generera en slumpmässig aktie
stock_name = st.sidebar.selectbox(
    "Välj en aktie:",
    options=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN", "META"],
)

if "stock_name" not in st.session_state:
    st.session_state["stock_name"] = stock_name
elif st.session_state["stock_name"] != stock_name:
    # If the user selects a new stock, reset data
    st.session_state["stock_name"] = stock_name
    st.session_state["t"] = None
    st.session_state["S"] = None
    st.session_state["order_book"] = None

# Simulera GBM för aktiens pris
if "S" not in st.session_state or st.session_state["S"] is None:
    initial_price = np.round(np.random.uniform(100, 300), 2)
    T = 1  # 1 dag
    dt = 1 / 252  # Daglig
    t, S = simulate_gbm(initial_price, mu=0.0005, sigma=0.02, T=T, dt=dt)
    st.session_state["t"] = t
    st.session_state["S"] = S
else:
    t = st.session_state["t"]
    S = st.session_state["S"]

# Dynamiskt justera y-axeln
min_price, max_price = np.min(S), np.max(S)
latest_price = S[-1]
# Spara senaste priset för aktien
st.session_state["latest_prices"][stock_name] = latest_price

# Skapa DataFrame för priser
df_prices = pd.DataFrame({"Tid": t, "Pris": S})

# Plotta prisets bana med Altair
st.subheader(f"Prisrörelse för {stock_name}")
st.write(f"Senaste pris för {stock_name}: **{latest_price:.2f} SEK**")

price_chart = alt.Chart(df_prices).mark_line().encode(
    x=alt.X('Tid', title='Tid'),
    y=alt.Y('Pris', scale=alt.Scale(
        domain=[min_price * 0.95, max_price * 1.05]), title='Pris (SEK)')
).properties(
    width='container',
    height=400
)

st.altair_chart(price_chart, use_container_width=True)

# Dynamisk orderbok
st.subheader("Orderbok")
order_book_placeholder = st.empty()

# Starta dynamisk orderbok
if st.session_state["order_book"] is None:
    current_price = latest_price
    order_book = generate_order_book(current_price)
    st.session_state["order_book"] = order_book
else:
    order_book = st.session_state["order_book"]

# Visa orderboken
with order_book_placeholder.container():
    st.table(order_book)

# Portfölj
st.sidebar.subheader("Portfölj")
if portfolio:
    portfolio_df = pd.DataFrame.from_dict(
        portfolio, orient="index", columns=["Antal"])
    # Lägg till senaste pris för varje aktie
    portfolio_df["Senaste pris"] = portfolio_df.index.map(
        lambda x: st.session_state["latest_prices"].get(x, 0))
    # Beräkna värde för varje aktie
    portfolio_df["Värde"] = portfolio_df["Antal"] * \
        portfolio_df["Senaste pris"]
    # Beräkna totalt värde
    total_value = portfolio_df["Värde"].sum()
    st.sidebar.dataframe(portfolio_df.style.format(
        {"Antal": "{:.0f}", "Senaste pris": "{:.2f}", "Värde": "{:.2f}"}))
    st.sidebar.write(f"**Totalt portföljvärde:** {total_value:.2f} SEK")
else:
    st.sidebar.write("Ingen aktie köpt än!")

# Dina Order
st.subheader("Dina Order")
price = st.number_input("Ange pris per aktie (SEK):",
                        min_value=0.01, step=0.01, format="%.2f")
volume = st.number_input("Ange antal aktier:", min_value=1, step=1)

if st.button("Lägg order"):
    executed, balance, portfolio, order_book = handle_buy(
        order_book, portfolio, balance, stock_name, price, volume
    )
    if executed:
        st.session_state["portfolio"] = portfolio
        st.session_state["balance"] = balance
        st.session_state["order_book"] = order_book
        # Uppdatera orderboken i UI
        with order_book_placeholder.container():
            st.table(order_book)

# Uppdatera session state
st.session_state["portfolio"] = portfolio
st.session_state["balance"] = balance
st.session_state["order_book"] = order_book
