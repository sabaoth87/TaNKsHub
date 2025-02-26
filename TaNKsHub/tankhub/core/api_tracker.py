import json
from datetime import datetime, timedelta
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class APIUsageTracker:
    """Track API usage statistics for external services."""
    
    def __init__(self):
        self.stats_file = Path('config/api_usage.json')
        self.usage_stats = {}
        self._load_stats()
        
    def _load_stats(self):
        """Load existing API stats from file."""
        try:
            # Create config directory if it doesn't exist
            self.stats_file.parent.mkdir(parents=True, exist_ok=True)
            
            if self.stats_file.exists():
                with open(self.stats_file, 'r') as f:
                    self.usage_stats = json.load(f)
                logger.info("Loaded API usage statistics")
            else:
                # Initialize with default structure
                self.usage_stats = {
                    "omdb": {
                        "daily_limit": 1000,  # Default OMDb free tier limit
                        "calls_today": 0,
                        "last_reset": datetime.now().strftime("%Y-%m-%d"),
                        "total_calls": 0,
                        "successful_calls": 0,
                        "failed_calls": 0,
                        "daily_history": {}  # Store daily usage counts
                    },
                    "tmdb": {
                        "daily_limit": 1000,  # Default TMDb limit
                        "calls_today": 0,
                        "last_reset": datetime.now().strftime("%Y-%m-%d"),
                        "total_calls": 0,
                        "successful_calls": 0,
                        "failed_calls": 0,
                        "daily_history": {}  # Store daily usage counts
                    }
                }
                self._save_stats()
                logger.info("Created default API usage statistics")
        except Exception as e:
            logger.error(f"Error loading API usage statistics: {str(e)}")
            # Create default stats on error
            self.usage_stats = {
                "omdb": {"daily_limit": 1000, "calls_today": 0, "last_reset": datetime.now().strftime("%Y-%m-%d"), "total_calls": 0, "successful_calls": 0, "failed_calls": 0, "daily_history": {}},
                "tmdb": {"daily_limit": 1000, "calls_today": 0, "last_reset": datetime.now().strftime("%Y-%m-%d"), "total_calls": 0, "successful_calls": 0, "failed_calls": 0, "daily_history": {}}
            }
    
    def _save_stats(self):
        """Save current API usage statistics to file."""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.usage_stats, f, indent=4)
            logger.info("Saved API usage statistics")
        except Exception as e:
            logger.error(f"Error saving API usage statistics: {str(e)}")
    
    def _check_day_reset(self, api_name):
        """Check if we need to reset the daily counter."""
        today = datetime.now().strftime("%Y-%m-%d")
        last_reset = self.usage_stats[api_name]["last_reset"]
        
        if today != last_reset:
            # It's a new day, store yesterday's count in history
            yesterday = datetime.strptime(last_reset, "%Y-%m-%d").strftime("%Y-%m-%d")
            yesterday_calls = self.usage_stats[api_name]["calls_today"]
            
            # Add to daily history
            self.usage_stats[api_name]["daily_history"][yesterday] = yesterday_calls
            
            # Keep only the last 30 days in history
            history = self.usage_stats[api_name]["daily_history"]
            if len(history) > 30:
                oldest_date = min(history.keys())
                del history[oldest_date]
            
            # Reset counter for today
            self.usage_stats[api_name]["calls_today"] = 0
            self.usage_stats[api_name]["last_reset"] = today
            self._save_stats()
    
    def record_api_call(self, api_name, success=True):
        """Record an API call with its outcome."""
        api_name = api_name.lower()
        if api_name not in self.usage_stats:
            # Initialize stats for new API
            self.usage_stats[api_name] = {
                "daily_limit": 1000,  # Default limit
                "calls_today": 0,
                "last_reset": datetime.now().strftime("%Y-%m-%d"),
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "daily_history": {}
            }
        
        # Check if day needs to be reset
        self._check_day_reset(api_name)
        
        # Update stats
        self.usage_stats[api_name]["calls_today"] += 1
        self.usage_stats[api_name]["total_calls"] += 1
        
        if success:
            self.usage_stats[api_name]["successful_calls"] += 1
        else:
            self.usage_stats[api_name]["failed_calls"] += 1
        
        # Save updated stats
        self._save_stats()
    
    def set_api_limit(self, api_name, limit):
        """Set the daily limit for an API."""
        api_name = api_name.lower()
        if api_name in self.usage_stats:
            self.usage_stats[api_name]["daily_limit"] = limit
            self._save_stats()
    
    def get_usage_stats(self, api_name=None):
        """Get usage statistics for specific API or all APIs."""
        if api_name:
            api_name = api_name.lower()
            if api_name in self.usage_stats:
                # Check if day needs to be reset before returning stats
                self._check_day_reset(api_name)
                return self.usage_stats[api_name]
            return None
        
        # Check all APIs for day reset
        for api in self.usage_stats:
            self._check_day_reset(api)
        
        return self.usage_stats
    
    def get_usage_percentage(self, api_name):
        """Get the percentage of daily limit used."""
        api_name = api_name.lower()
        if api_name in self.usage_stats:
            self._check_day_reset(api_name)
            limit = self.usage_stats[api_name]["daily_limit"]
            used = self.usage_stats[api_name]["calls_today"]
            
            if limit > 0:
                return (used / limit) * 100
        return 0
    
    def is_limit_reached(self, api_name):
        """Check if the daily limit has been reached."""
        api_name = api_name.lower()
        if api_name in self.usage_stats:
            self._check_day_reset(api_name)
            limit = self.usage_stats[api_name]["daily_limit"]
            used = self.usage_stats[api_name]["calls_today"]
            
            return used >= limit
        return False
    
    def get_history_data(self, api_name, days=7):
        """Get historical usage data for charts."""
        api_name = api_name.lower()
        if api_name not in self.usage_stats:
            return []
            
        history = self.usage_stats[api_name]["daily_history"]
        today = datetime.now().date()
        
        # Include today's data
        data = [{
            "date": today.strftime("%Y-%m-%d"),
            "calls": self.usage_stats[api_name]["calls_today"]
        }]
        
        # Add historical data for the requested number of days
        for i in range(1, days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            if date in history:
                data.append({
                    "date": date,
                    "calls": history[date]
                })
            else:
                data.append({
                    "date": date,
                    "calls": 0
                })
        
        # Sort by date
        return sorted(data, key=lambda x: x["date"])