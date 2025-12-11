from neo4j_client import run_query

print(run_query("RETURN 'Aura is connected!' AS msg")[0]["msg"])
