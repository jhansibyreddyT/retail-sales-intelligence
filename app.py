import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Retail Sales Intelligence", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR EXECUTIVE LOOK ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; border-radius: 10px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .insight-card { background-color: #e3f2fd; border-left: 5px solid #2196f3; padding: 20px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def load_data(sales_file, master_file):
    if sales_file and master_file:
        df_sales = pd.read_excel(sales_file)
        df_master = pd.read_excel(master_file)
        
        # 1. FIX: Convert dates and handle "invalid-date" strings by coercing them to NaT
        df_sales['week_start_date'] = pd.to_datetime(df_sales['week_start_date'], errors='coerce')
        
        # 2. FIX: Drop rows where the date is now NaT (invalid data)
        before_count = len(df_sales)
        df_sales = df_sales.dropna(subset=['week_start_date'])
        after_count = len(df_sales)
        
        # Optional: Show a warning in the app if bad data was removed
        if before_count > after_count:
            st.sidebar.warning(f"⚠️ Removed {before_count - after_count} rows with invalid dates.")
        
        # 3. Preprocessing numeric columns
        df_sales['gross_sales'] = pd.to_numeric(df_sales['gross_sales'], errors='coerce').fillna(0)
        df_sales['discount_amount'] = pd.to_numeric(df_sales['discount_amount'], errors='coerce').fillna(0)
        
        # Impute missing net_sales
        df_sales['net_sales'] = df_sales['net_sales'].fillna(df_sales['gross_sales'] - df_sales['discount_amount'])
        
        # 4. Merge with master for metadata consistency
        df = pd.merge(df_sales, df_master, on='store_id', how='left', suffixes=('', '_ref'))
        return df
    return None

# --- SIDEBAR: UPLOAD & FILTERS ---
st.sidebar.header("📂 Data Ingestion")
sales_file = st.sidebar.file_uploader("Upload Weekly Sales (.xlsx)", type=["xlsx"])
master_file = st.sidebar.file_uploader("Upload Store Master (.xlsx)", type=["xlsx"])

df = load_data(sales_file, master_file)

if df is not None:
    st.sidebar.header("🔍 Global Filters")
    
    # Filter Logic
    regions = st.sidebar.multiselect("Region", options=df['region'].unique(), default=df['region'].unique())
    cities = st.sidebar.multiselect("City", options=df[df['region'].isin(regions)]['city'].unique())
    formats = st.sidebar.multiselect("Store Format", options=df['store_format'].unique(), default=df['store_format'].unique())
    categories = st.sidebar.multiselect("Product Category", options=df['product_category'].unique(), default=df['product_category'].unique())
    
    # Date Filter
    min_date = df['week_start_date'].min().to_pydatetime()
    max_date = df['week_start_date'].max().to_pydatetime()
    date_range = st.sidebar.date_input("Date Range", value=[min_date, max_date])

    # Apply Filters
    mask = (
        df['region'].isin(regions) &
        df['store_format'].isin(formats) &
        df['product_category'].isin(categories) &
        (df['week_start_date'] >= pd.Timestamp(date_range[0])) &
        (df['week_start_date'] <= pd.Timestamp(date_range[1]))
    )
    if cities:
        mask = mask & (df['city'].isin(cities))
        
    filtered_df = df[mask]

    # --- MAIN DASHBOARD ---
    st.title("📊 Retail Sales Intelligence App")
    st.markdown("### Executive Performance Overview")

    # --- KPI CALCULATIONS ---
    total_net_sales = filtered_df['net_sales'].sum()
    total_target = filtered_df['sales_target'].sum()
    target_ach_rate = (total_net_sales / total_target * 100) if total_target > 0 else 0
    atv = total_net_sales / filtered_df['transactions'].sum() if filtered_df['transactions'].sum() > 0 else 0
    conv_rate = (filtered_df['transactions'].sum() / filtered_df['footfall'].sum() * 100) if filtered_df['footfall'].sum() > 0 else 0
    return_rate = (filtered_df['returns_amount'].sum() / total_net_sales * 100) if total_net_sales > 0 else 0
    discount_rate = (filtered_df['discount_amount'].sum() / filtered_df['gross_sales'].sum() * 100) if filtered_df['gross_sales'].sum() > 0 else 0

    # KPI ROW
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Net Sales", f"₹{total_net_sales:,.0f}")
    col2.metric("Target Ach. %", f"{target_ach_rate:.1f}%")
    col3.metric("ATV", f"₹{atv:,.2f}")
    col4.metric("Conv. Rate", f"{conv_rate:.1f}%")
    col5.metric("Return Rate", f"{return_rate:.1f}%")
    col6.metric("Discount Rate", f"{discount_rate:.1f}%")

    st.divider()

    # --- VISUAL ANALYTICS ---
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader("Weekly Sales Trend")
        trend_df = filtered_df.groupby('week_start_date')[['net_sales', 'sales_target']].sum().reset_index()
        fig_trend = px.line(trend_df, x='week_start_date', y=['net_sales', 'sales_target'], 
                            labels={'value': 'Amount', 'week_start_date': 'Week'},
                            color_discrete_map={'net_sales': '#1f77b4', 'sales_target': '#ff7f0e'})
        st.plotly_chart(fig_trend, use_container_width=True)

    with row1_col2:
        st.subheader("Regional Performance")
        reg_df = filtered_df.groupby('region').agg({'net_sales': 'sum', 'sales_target': 'sum'}).reset_index()
        reg_df['Ach %'] = (reg_df['net_sales'] / reg_df['sales_target'] * 100).round(1)
        fig_reg = px.bar(reg_df, x='region', y='net_sales', text='Ach %',
                         title="Net Sales by Region (Labels show Target Achievement %)")
        st.plotly_chart(fig_reg, use_container_width=True)

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.subheader("Category Performance & Return Risk")
        cat_df = filtered_df.groupby('product_category').agg({'net_sales': 'sum', 'returns_amount': 'sum'}).reset_index()
        cat_df['Return Rate %'] = (cat_df['returns_amount'] / cat_df['net_sales'] * 100).round(1)
        fig_cat = px.bar(cat_df, x='net_sales', y='product_category', orientation='h', 
                         color='Return Rate %', color_continuous_scale='Reds')
        st.plotly_chart(fig_cat, use_container_width=True)

    with row2_col2:
        st.subheader("Stockout vs. Inventory Levels")
        # Aggregated by store for clarity
        inv_df = filtered_df.groupby('store_name').agg({'stockouts': 'sum', 'inventory_on_hand': 'mean'}).reset_index()
        fig_inv = px.scatter(inv_df, x='inventory_on_hand', y='stockouts', text='store_name', size='stockouts',
                             hover_name='store_name', title="Stockout Incidents vs. Avg Inventory")
        st.plotly_chart(fig_inv, use_container_width=True)

    # --- STORE LEADERBOARD ---
    st.subheader("Store Leaderboard (Target Achievement %)")
    store_lead = filtered_df.groupby('store_name').agg({'net_sales': 'sum', 'sales_target': 'sum'}).reset_index()
    store_lead['Achievement %'] = (store_lead['net_sales'] / store_lead['sales_target'] * 100).round(1)
    store_lead = store_lead.sort_values(by='Achievement %', ascending=False)
    
    fig_lead = px.bar(store_lead, x='Achievement %', y='store_name', orientation='h',
                      color='Achievement %', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_lead, use_container_width=True)

    # --- ACTIONABLE INSIGHTS ---
    st.markdown("### 💡 Business Insights Summary")
    
    # Logic for insights
    best_region = reg_df.loc[reg_df['net_sales'].idxmax(), 'region']
    worst_region = reg_df.loc[reg_df['net_sales'].idxmin(), 'region']
    underperforming_stores = store_lead[store_lead['Achievement %'] < 90]
    high_return_cats = cat_df.sort_values(by='Return Rate %', ascending=False).head(2)
    
    insight_text = f"""
    <div class="insight-card">
    <b>Top Performance:</b> The <b>{best_region}</b> region is leading in net sales, while <b>{worst_region}</b> requires strategic focus.<br><br>
    <b>Inventory Alert:</b> Stores with high stockouts despite inventory levels suggest distribution inefficiencies.<br><br>
    <b>Return Risk:</b> High return rates observed in <b>{', '.join(high_return_cats['product_category'].tolist())}</b>. Immediate quality check or description audit recommended.<br><br>
    <b>Target Warning:</b> {len(underperforming_stores)} stores are performing below 90% of their target.
    </div>
    """
    st.markdown(insight_text, unsafe_allow_html=True)

    # --- EXPORT SECTION ---
    st.divider()
    col_dl1, col_dl2 = st.columns(2)
    
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    col_dl1.download_button("📥 Download Filtered Sales Data", data=csv_data, file_name="filtered_retail_data.csv", mime="text/csv")
    
    # Summary Report Export
    summary_df = store_lead.to_csv(index=False).encode('utf-8')
    col_dl2.download_button("📋 Export Store Performance Summary", data=summary_df, file_name="store_performance_report.csv", mime="text/csv")

else:
    st.info("👋 Welcome! Please upload 'retail_weekly_sales.xlsx' and 'store_master.xlsx' in the sidebar to begin.")
    
    # Mock Data Creator for the user if they don't have files
    if st.checkbox("Show Sample Data Structure Required"):
        st.write("Required Columns: week_start_date, store_id, region, product_category, gross_sales, sales_target, etc.")
