from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, ReadServiceUnavailable, SessionExpired
from dotenv import load_dotenv
import os
import time
load_dotenv()

class GraphClient:
    def __init__(self, max_retries=3, retry_delay=2):
        URI = os.getenv("NEO4J_URI")
        AUTH = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        
        # Check if environment variables are set
        if not URI:
            raise ValueError("NEO4J_URI environment variable is not set. Please check your .env file.")
        if not AUTH[0] or not AUTH[1]:
            raise ValueError("NEO4J_USER or NEO4J_PASSWORD environment variable is not set. Please check your .env file.")
        
        self.URI = URI
        self.AUTH = AUTH
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Try to connect with retries
        for attempt in range(max_retries):
            try:
                self.driver = GraphDatabase.driver(URI, auth=AUTH) 
                self.driver.verify_connectivity()
                return  # Success, exit retry loop
            except (ReadServiceUnavailable, SessionExpired) as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Neo4j service unavailable (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    raise ConnectionError(
                        f"❌ Failed to connect to Neo4j after {max_retries} attempts.\n"
                        f"Error: {type(e).__name__} - {str(e)}\n\n"
                        f"🔍 Possible causes:\n"
                        f"  1. Neo4j Aura instance is PAUSED (most common)\n"
                        f"     → Check Neo4j Aura Console: https://console.neo4j.io/\n"
                        f"     → Resume the instance if it's paused\n"
                        f"  2. Neo4j Aura instance has EXPIRED\n"
                        f"     → Free tier instances expire after inactivity\n"
                        f"     → Create a new instance or upgrade to paid tier\n"
                        f"  3. No read service available\n"
                        f"     → Instance might be in maintenance or restarting\n"
                        f"     → Wait a few minutes and try again\n"
                        f"  4. Network connectivity issues\n"
                        f"     → Check your internet connection\n\n"
                        f"💡 Solution:\n"
                        f"  1. Go to: https://console.neo4j.io/\n"
                        f"  2. Check if your instance is running (not paused)\n"
                        f"  3. If paused, click 'Resume' to start it\n"
                        f"  4. Wait 1-2 minutes for the instance to fully start\n"
                        f"  5. Try running your script again\n"
                    ) from e
            except ServiceUnavailable as e:
                error_msg = str(e)
                if "getaddrinfo failed" in error_msg or "DNS resolve" in error_msg:
                    raise ConnectionError(
                        f"Failed to connect to Neo4j at {URI}\n"
                        f"Possible causes:\n"
                        f"  1. No internet connection\n"
                        f"  2. DNS resolution failure (check your network/DNS settings)\n"
                        f"  3. Neo4j server is down or unreachable\n"
                        f"  4. Firewall blocking the connection\n"
                        f"  5. Incorrect NEO4J_URI in .env file\n\n"
                        f"Original error: {error_msg}"
                    ) from e
                else:
                    raise ConnectionError(
                        f"Failed to connect to Neo4j at {URI}\n"
                        f"Error: {error_msg}\n"
                        f"Please check:\n"
                        f"  1. Neo4j server is running\n"
                        f"  2. NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are correct in .env file"
                    ) from e
        
    def session(self):
        return self.driver.session()
    
    def getDriver(self):
        return self.driver