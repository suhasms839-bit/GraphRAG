from neo4j import GraphDatabase

# Using your explicit database routing parameters
uri = "neo4j+s://ae363b93.databases.neo4j.io"
user = "ae363b93" 
password = "TmA0xpZxBZxjLFuWRYHQmRkk4cqJTUuM730egUWhcI4"

print("Attempting connection to Neo4j using explicit user profile...")
try:
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        print("🚀 SUCCESS: Connected to Fresh Instance!")
except Exception as e:
    print(f"❌ Connection failed: {e}")
