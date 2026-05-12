import matplotlib.pyplot as plt
import os

def generate_war_charts(data, base_name):
    """Generates visual charts and returns their file paths."""
    
    # Sort members by hits and respect
    sorted_by_hits = sorted(data['members'], key=lambda x: x['war_hits'], reverse=True)
    sorted_by_rep = sorted(data['members'], key=lambda x: x['rep_gained'], reverse=True)
    
    # Use a dark theme so it looks good on Discord
    plt.style.use('dark_background')
    
    # ==========================================
    # CHART 1: Top 10 Hitters (Bar Chart)
    # ==========================================
    top_10 = sorted_by_hits[:10]
    names = [m['name'] for m in top_10]
    hits = [m['war_hits'] for m in top_10]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(names, hits, color='#92D050') # Lime Green
    plt.title(f"Top 10 Hitters vs {data['opponent_name']}", fontsize=16, fontweight='bold')
    plt.ylabel("War Hits", fontsize=12)
    plt.xticks(rotation=45, ha='right')
    
    # Add numbers on top of bars
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5, int(yval), ha='center', va='bottom', color='white')
        
    plt.tight_layout()
    bar_chart_path = f"{base_name}_bar.png"
    plt.savefig(bar_chart_path)
    plt.close()

    # ==========================================
    # CHART 2: Respect Share (Pie Chart)
    # ==========================================
    # Calculate how much respect the Top 5 got vs everyone else
    top_5_rep = sum(m['rep_gained'] for m in sorted_by_rep[:5])
    total_rep = data.get('total_rep_after', sum(m['rep_gained'] for m in data['members']))
    rest_rep = total_rep - top_5_rep

    # Only generate if there is actual respect to show
    pie_chart_path = f"{base_name}_pie.png"
    if total_rep > 0:
        plt.figure(figsize=(8, 8))
        labels = ['Top 5 Hitters', 'Rest of Faction']
        sizes = [top_5_rep, rest_rep]
        colors = ['#92D050', '#555555'] # Lime Green for Top 5, Grey for the rest
        explode = (0.1, 0)  # slightly "explode" the Top 5 slice
        
        plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', 
                shadow=True, startangle=140, textprops={'fontsize': 14, 'fontweight': 'bold'})
        
        plt.title("Faction Respect Share", fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(pie_chart_path)
        plt.close()
        
        return [bar_chart_path, pie_chart_path]

    # If respect is 0 (war just started), just return the bar chart
    return [bar_chart_path]