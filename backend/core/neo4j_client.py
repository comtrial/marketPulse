from neo4j import GraphDatabase

from core.config import settings

neo4j_driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password),
)


def get_neo4j_session():
    return neo4j_driver.session()


def verify_neo4j_connection() -> bool:
    try:
        with neo4j_driver.session() as session:
            result = session.run("RETURN 1 AS n")
            return result.single()["n"] == 1
    except Exception:
        return False
