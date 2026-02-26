"""
Script to verify data stored in Neo4j database.
Run this to check if your indexing data is actually stored in Neo4j.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

def _load_env() -> None:
    """Load env from src/.env if present."""
    src_dir = Path(__file__).resolve().parents[1]
    env_path = src_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

def verify_data():
    """Query Neo4j to verify stored data."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")
    
    if not uri or not user or not pwd:
        print("❌ Missing Neo4j credentials in .env file")
        return
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        driver.verify_connectivity()
        
        with driver.session() as session:
            # Count nodes by type
            print("\n" + "="*60)
            print("📊 NEO4J DATA VERIFICATION")
            print("="*60)
            
            # Count Documentation nodes
            result = session.run("MATCH (d:Documentation) RETURN count(d) as count")
            doc_count = result.single()["count"]
            print(f"\n📄 Documentation nodes: {doc_count}")
            
            # Count Version nodes
            result = session.run("MATCH (v:Version) RETURN count(v) as count")
            version_count = result.single()["count"]
            print(f"🔢 Version nodes: {version_count}")
            
            # Count Content nodes
            result = session.run("MATCH (c:Content) RETURN count(c) as count")
            content_count = result.single()["count"]
            print(f"📦 Content nodes: {content_count}")
            
            # Count Category nodes
            result = session.run("MATCH (cat:Category) RETURN count(cat) as count")
            category_count = result.single()["count"]
            print(f"🏷️  Category nodes: {category_count}")
            
            # Count Change nodes
            result = session.run("MATCH (ch:Change) RETURN count(ch) as count")
            change_count = result.single()["count"]
            print(f"🔄 Change nodes: {change_count}")
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]
            print(f"🔗 Relationships: {rel_count}")
            
            # Show sample Documentation nodes
            print("\n" + "-"*60)
            print("📋 Sample Documentation nodes:")
            print("-"*60)
            result = session.run("MATCH (d:Documentation) RETURN d.name as name, d.description as desc LIMIT 5")
            for record in result:
                print(f"  • {record['name']}")
                if record['desc']:
                    desc = record['desc'][:80] + "..." if len(record['desc']) > 80 else record['desc']
                    print(f"    {desc}")
            
            # Show sample Version nodes
            print("\n" + "-"*60)
            print("🔢 Sample Version nodes:")
            print("-"*60)
            result = session.run("""
                MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)
                RETURN d.name as doc, v.version as version
                LIMIT 5
            """)
            for record in result:
                print(f"  • {record['doc']} → Version: {record['version']}")
            
            # Show relationships summary
            print("\n" + "-"*60)
            print("🔗 Relationship types:")
            print("-"*60)
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """)
            for record in result:
                print(f"  • {record['rel_type']}: {record['count']}")
            
            print("\n" + "="*60)
            if doc_count > 0 or version_count > 0 or content_count > 0:
                print("✅ Data is stored in Neo4j!")
            else:
                print("⚠️  No data found in Neo4j. Indexing may not have completed.")
            print("="*60 + "\n")
        
        driver.close()
        
    except Exception as e:
        print(f"❌ Error connecting to Neo4j: {e}")

def print_connection_info():
    """Print connection info for Neo4j Browser."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    
    if not uri or not user:
        print("❌ Missing Neo4j credentials in .env file")
        return
    
    print("\n" + "="*60)
    print("🔗 INFO KONEKSI UNTUK NEO4J BROWSER")
    print("="*60)
    print(f"\nURI: {uri}")
    print(f"Username: {user}")
    print(f"\n📝 Cara akses:")
    print("1. Buka: https://console.neo4j.io/")
    print("2. Login dengan akun Neo4j Aura Anda")
    print("3. Pilih instance database Anda")
    print("4. Klik 'Open' atau 'Query' untuk buka Neo4j Browser")
    print("\nAtau langsung akses: https://browser.neo4j.io/")
    print("   Masukkan kredensial di atas")
    print("\n" + "="*60 + "\n")
    
    print("📋 QUERY CYPHER UNTUK MELIHAT GRAPH:")
    print("-"*60)
    print("\n1. Lihat semua node dan relationship:")
    print("   MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50")
    
    print("\n2. Lihat struktur Documentation → Version → Content:")
    print("   MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)-[:HAS_CONTENT]->(c:Content)")
    print("   RETURN d, v, c LIMIT 20")
    
    print("\n3. Lihat semua Documentation dengan Versinya:")
    print("   MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)")
    print("   RETURN d.name as Documentation, collect(v.version) as Versions")
    
    print("\n4. Lihat Category dan Documentation:")
    print("   MATCH (cat:Category)-[:CONTAINS]->(d:Documentation)")
    print("   RETURN cat, d")
    
    print("\n5. Lihat Version Chain (NEXT_VERSION):")
    print("   MATCH path = (v1:Version)-[:NEXT_VERSION*]->(v2:Version)")
    print("   RETURN path LIMIT 10")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    import sys
    _load_env()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--info":
        print_connection_info()
    else:
        verify_data()
        print("\n💡 Tip: Jalankan dengan '--info' untuk melihat info koneksi Neo4j Browser")
        print("   python src/util/verify_neo4j_data.py --info")

