import os
import io
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from datetime import datetime, timedelta

class AnalyticsVisualization:

    
    @staticmethod
    def generate_class_distribution_chart(class_counts: Dict[str, int], title: str = "Object Class Distribution") -> bytes:

        if not class_counts:
            # Create empty chart
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=14)
            ax.axis('off')
        else:
            # Create pie chart
            fig, ax = plt.subplots(figsize=(8, 6))
            labels = list(class_counts.keys())
            sizes = list(class_counts.values())
            
            # Sort by count
            sorted_data = sorted(zip(labels, sizes), key=lambda x: x[1], reverse=True)
            labels = [item[0] for item in sorted_data]
            sizes = [item[1] for item in sorted_data]
            
            # If there are too many classes, group the smaller ones
            if len(labels) > 7:
                main_labels = labels[:6]
                main_sizes = sizes[:6]
                other_size = sum(sizes[6:])
                
                labels = main_labels + ["Other"]
                sizes = main_sizes + [other_size]
            
            # Create pie chart
            wedges, texts, autotexts = ax.pie(
                sizes, 
                labels=labels, 
                autopct='%1.1f%%',
                textprops={'fontsize': 10},
                shadow=True, 
                startangle=90
            )
            
            # Equal aspect ratio ensures that pie is drawn as a circle
            ax.axis('equal')
        
        # Set title
        plt.title(title)
        
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        
        return buf.getvalue()
    
    @staticmethod
    def generate_detection_timeline(detection_counts: List[Tuple[datetime, int]], 
                                   title: str = "Detections Over Time") -> bytes:

        if not detection_counts:
            # Create empty chart
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=14)
            ax.axis('off')
        else:
            # Create line chart
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Extract data
            timestamps = [item[0] for item in detection_counts]
            counts = [item[1] for item in detection_counts]
            
            # Plot data
            ax.plot(timestamps, counts, marker='o', linestyle='-', linewidth=2, markersize=6)
            
            # Format x-axis as time
            ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H:%M:%S'))
            fig.autofmt_xdate()
            
            # Add labels and grid
            ax.set_xlabel('Time')
            ax.set_ylabel('Number of Detections')
            ax.grid(True, alpha=0.3)
        
        # Set title
        plt.title(title)
        
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        
        return buf.getvalue()
    
    @staticmethod
    def generate_heatmap_image(heatmap: np.ndarray, colormap: str = 'jet', alpha: float = 0.7) -> np.ndarray:

        if heatmap is None or heatmap.size == 0:
            # Return empty image
            return np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Normalize heatmap
        if np.max(heatmap) > 0:
            heatmap = heatmap / np.max(heatmap)
        
        # Convert to colormap
        cmap = plt.get_cmap(colormap)
        heatmap_rgb = cmap(heatmap)[:, :, :3]  # Remove alpha channel
        
        # Convert to uint8
        heatmap_rgb = (heatmap_rgb * 255).astype(np.uint8)
        
        return heatmap_rgb
    
    @staticmethod
    def generate_weekly_activity_chart(daily_counts: Dict[str, int], title: str = "Weekly Activity") -> bytes:

        # Ensure all days are represented
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        counts = [daily_counts.get(day, 0) for day in days]
        
        # Create bar chart
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(days, counts, color='skyblue', edgecolor='navy')
        
        # Add count labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                   f'{int(height)}', ha='center', va='bottom')
        
        # Add labels and grid
        ax.set_xlabel('Day of Week')
        ax.set_ylabel('Number of Detections')
        ax.grid(True, alpha=0.3, axis='y')
        
        # Set title
        plt.title(title)
        
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        
        return buf.getvalue()
    
    @staticmethod
    def generate_detection_summary(stats: Dict) -> bytes:

        # Create figure with multiple subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
        
        # Top part: Class distribution
        class_counts = stats.get("class_counts", {})
        if class_counts:
            labels = list(class_counts.keys())
            sizes = list(class_counts.values())
            
            # Sort by count
            sorted_data = sorted(zip(labels, sizes), key=lambda x: x[1], reverse=True)
            labels = [item[0] for item in sorted_data]
            sizes = [item[1] for item in sorted_data]
            
            # If there are too many classes, group the smaller ones
            if len(labels) > 7:
                main_labels = labels[:6]
                main_sizes = sizes[:6]
                other_size = sum(sizes[6:])
                
                labels = main_labels + ["Other"]
                sizes = main_sizes + [other_size]
            
            # Create pie chart
            wedges, texts, autotexts = ax1.pie(
                sizes, 
                labels=labels, 
                autopct='%1.1f%%',
                textprops={'fontsize': 10},
                shadow=True, 
                startangle=90
            )
            
            # Equal aspect ratio ensures that pie is drawn as a circle
            ax1.axis('equal')
            ax1.set_title("Class Distribution")
        else:
            ax1.text(0.5, 0.5, "No class data available", ha='center', va='center', fontsize=14)
            ax1.axis('off')
        
        # Bottom part: Summary text
        ax2.axis('off')
        summary_text = f"""
        Detection Summary:
        
        Total Detections: {stats.get('detection_count', 0)}
        Total Frames Processed: {stats.get('frame_count', 0)}
        Detection Rate: {stats.get('detection_count', 0) / max(1, stats.get('frame_count', 1)):.2%}
        
        Top Classes:
        """
        
        # Add top classes if available
        if class_counts:
            sorted_classes = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)
            for i, (class_name, count) in enumerate(sorted_classes[:5]):
                summary_text += f"  {i+1}. {class_name}: {count}\n"
        
        ax2.text(0.1, 0.9, summary_text, fontsize=12, va='top', ha='left', 
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Adjust layout
        plt.tight_layout()
        
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        
        return buf.getvalue() 