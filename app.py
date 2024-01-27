from flask import Flask, jsonify, request
from neo4j import GraphDatabase

app = Flask(__name__)
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "test1234"), database="neo4j")

def get_employees(tx):
    query = "MATCH (m:Employee) RETURN m"
    results = tx.run(query).data()
    employees = [{'name': result['m']['name'], 'position': result['m']['position']} for result in results]
    return employees

@app.route('/employees', methods=['GET'])
def get_employees_route():
    with driver.session() as session:
        employees = session.execute_read(get_employees)

    response = {'employees': employees}
    return jsonify(response)

def get_subordinates(tx, name):
    query = "MATCH (m:Employee {name: $name})-[r]->(n:Department) RETURN m, n"
    result = tx.run(query, name=name).data()
    if not result:
        return None
    elif result[0]['m']['position'] != "boss":
        return None
    else:
        dep_name = result[0]['n']['name']
        query2 = "MATCH (m:Employee)-[:WORKS_IN]->(n:Department {name: $dep_name}) RETURN m"
        result2 = tx.run(query2, dep_name=dep_name).data()
        workers = [{'name': result['m']['name'], 'position': result['m']['position']} for result in result2]
        return workers

@app.route('/employees/<string:id>/subordinates', methods=['GET'])
def get_subordinates_route(id):
    name = id
    with driver.session() as session:
        employee = session.execute_read(get_subordinates, name)

        if not employee:
            response = {'message': 'No subordinates'}
            return jsonify(response), 404
        response = employee
        return jsonify(response)

def get_dep_info(tx, name):
    query = "MATCH (m:Employee {name: $name})-[r]->(n:Department) RETURN n"
    result = tx.run(query, name=name).data()
    if not result:
        return None
    else:
        dep_name = result[0]['n']['name']
        query2 = "MATCH (m:Employee)-[r]->(n:Department {name: $dep_name}) RETURN m"
        result2 = tx.run(query2, dep_name=dep_name).data()
        boss = None
        workers = 0
        for res in result2:
            workers += 1
            if res['m']['position'] == "boss":
                boss = res['m']['name']
        return {"dep_name": dep_name, "dep_boss": boss, "workers_nr": workers}

@app.route('/employees/<string:id>/department', methods=['GET'])
def get_dep_info_route(id):
    name = id
    with driver.session() as session:
        employee = session.execute_read(get_dep_info, name)

        if not employee:
            response = {'message': 'No such worker'}
            return jsonify(response), 404
        response = employee
        return jsonify(response)

def get_departments(tx):
    query = "MATCH (m:Department) RETURN m"
    results = tx.run(query).data()
    deps = [{'name': result['m']['name']} for result in results]
    return deps

@app.route('/departments', methods=['GET'])
def get_departments_route():
    with driver.session() as session:
        departments = session.execute_read(get_departments)
    response = {'departments': departments}
    return jsonify(response)

def get_workers(tx, name):
    query = "MATCH (m:Department) WHERE m.name=$name RETURN m"
    result = tx.run(query, name=name).data()
    if not result:
        return None
    else:
        dep_name = result[0]['m']['name']
        query2 = "MATCH (m:Employee)-[r]->(n:Department {name: $dep_name}) RETURN m"
        result2 = tx.run(query2, dep_name=dep_name).data()
        workers = [{'name': result['m']['name'], 'position': result['m']['position']} for result in result2]
        return workers

@app.route('/departments/<string:id>/employees', methods=['GET'])
def get_workers_route(id):
    dep_name = id
    with driver.session() as session:
        dep = session.execute_read(get_workers, dep_name)

        if not dep:
            response = {'message': 'No such department'}
            return jsonify(response), 404
        response = dep
        return jsonify(response)

def add_employee(tx, name, pos, dep):
    query = "MATCH (m:Employee {name: $name}) RETURN m"
    result = tx.run(query, name=name).data()
    if result:
        return None
    else:
        if pos == "boss":
            query = "MATCH (m:Department) WHERE m.name=$dep CREATE (n:Employee {name: $name, position: $pos})-[:MANAGES]->(m)"
        else:
            query = "MATCH (m:Department) WHERE m.name=$dep CREATE (n:Employee {name: $name, position: $pos})-[:WORKS_IN]->(m)"
        tx.run(query, name=name, pos=pos, dep=dep)
        return {'name': name, 'pos': pos, 'dep': dep}


@app.route('/employees', methods=['POST'])
def add_employee_route():
    data = request.get_json()
    name = data.get("name")
    position = data.get("position")
    department = data.get("department")
    if name and position and department:
        with driver.session() as session:
            employee = session.execute_write(add_employee, name, position, department)

        if not employee:
            response = {'message': 'Same name error probably'}
            return jsonify(response), 404
        response = {'status': 'success'}
        return jsonify(response)
    else:
        response = {'message': 'Need more information'}
        return jsonify(response)


def update_employee(tx, name, new_name, position, department):
    query0 = "MATCH (m:Employee)-[r]->(n:Department) WHERE m.name=$name RETURN m, n"
    result = tx.run(query0, name=name).data()

    if not result:
        return None
    else:
        if department != result[0]['n']['name']:
            query1 = "MATCH (n:Employee) WHERE n.name=$name DETACH DELETE n"
            tx.run(query1, name=name)
            query2 = "MATCH (m:Department) WHERE m.name=$department CREATE (n:Employee {name: $new_name, position: $position})-[:WORKS_IN]->(m)"
            tx.run(query2, new_name=new_name, position=position, department=department)
        else:
            query4 = "MATCH (m:Employee) WHERE m.name=$name SET m.name=$new_name, m.position=$position"
            tx.run(query4, name=name, new_name=new_name, position=position, department=department)
        return {"updated": new_name}


@app.route('/employees/<string:id>', methods=['PUT'])
def update_employee_route(id):
    name = id
    data = request.get_json()
    new_name = data.get("name")
    position = data.get("position")
    department = data.get("department")
    if new_name and position and department:
        with driver.session() as session:
            employee = session.execute_write(update_employee, name, new_name, position, department)
        if not employee:
            response = {'message': 'No such employee'}
            return jsonify(response), 404
        response = employee
        return jsonify(response)
    else:
        response = {'message': 'Need more information'}
        return jsonify(response)


def delete_employee(tx, name):
    query = "MATCH (m:Employee) WHERE m.name=$name RETURN m"
    result = tx.run(query, name=name).data()

    if not result:
        return None
    elif result[0]['m']['position'] == "boss":
        query = "MATCH (m:Employee {name: $name})-[:MANAGES]->(n:Department) DETACH DELETE m, n"
        tx.run(query, name=name)
        return {"deleted": name}
    else:
        query = "MATCH (m:Employee {name: $name}) DETACH DELETE m"
        tx.run(query, name=name)
        return {"deleted": name}

@app.route('/employees/<string:id>', methods=['DELETE'])
def delete_employee_route(id):
    with driver.session() as session:
        employee = session.execute_write(delete_employee, id)

    if not employee:
        response = {'message': 'Employee not found'}
        return jsonify(response), 404
    else:
        response = employee
        return jsonify(response)

if __name__ == '__main__':
    app.run()

