# -*- coding: utf-8 -*-

"""
Testing DatabaseMeta, TableMeta
"""

import unittest
from etl_manager.meta import DatabaseMeta, TableMeta, read_database_folder, read_table_json, _agnostic_to_glue_spark_dict
from etl_manager.utils import _end_with_slash, _validate_string, _glue_client, read_json, _remove_final_slash
from etl_manager.etl import GlueJob
import boto3
import tempfile
import os
import urllib, json

class UtilsTest(unittest.TestCase) :
    """
    Test packages utilities functions
    """
    def test_meta_funs(self) :
        self.assertEqual(_end_with_slash('no_slash'), 'no_slash/')
        self.assertEqual(_end_with_slash('slash/'), 'slash/')
        self.assertRaises(ValueError, _validate_string, "UPPER")
        self.assertRaises(ValueError, _validate_string, "test:!@")
        self.assertEqual(_validate_string("test:!@", ":!@"), None)
        self.assertEqual(_remove_final_slash('hello/'), 'hello')
        self.assertEqual(_remove_final_slash('hello'), 'hello')

class GlueTest(unittest.TestCase) :
    """
    Test the GlueJob class
    """
    def test_init(self) :
        g = GlueJob('example/glue_jobs/simple_etl_job/', bucket = 'alpha-everyone', job_role = 'alpha_user_isichei', job_arguments={'--test_arg': 'this is a test'})

        self.assertEqual(g.resources, ['example/glue_jobs/simple_etl_job/glue_resources/employees.json', 'example/glue_jobs/shared_job_resources/glue_resources/teams.json'])
        self.assertEqual(g.py_resources, ['example/glue_jobs/shared_job_resources/glue_py_resources/my_dummy_utils.zip'])
        self.assertEqual(g.job_name, 'simple_etl_job')
        self.assertEqual(g.bucket, "alpha-everyone")
        self.assertEqual(g.job_role, 'alpha_user_isichei')
        self.assertEqual(g.github_zip_urls, ['https://github.com/moj-analytical-services/gluejobutils/archive/master.zip'])
        self.assertEqual(g.job_arguments["--test_arg"], 'this is a test')
        self.assertEqual(g.github_py_resources, [])
        self.assertEqual(g.max_retries, 0)
        self.assertEqual(g.max_concurrent_runs, 1)
        self.assertEqual(g.allocated_capacity, 2)

        g2 = GlueJob('example/glue_jobs/simple_etl_job/', bucket = 'alpha-everyone', job_role = 'alpha_user_isichei', include_shared_job_resources=False)
        self.assertEqual(g2.resources, ['example/glue_jobs/simple_etl_job/glue_resources/employees.json'])
        self.assertEqual(g2.py_resources, [])

        self.assertTrue("_GlueJobs_" in g2.job_arguments['--metadata_base_path'])

    def test_glue_param_error(self) :
        g = GlueJob('example/glue_jobs/simple_etl_job/', bucket = 'alpha-everyone', job_role = 'alpha_user_isichei', job_arguments={'--test_arg': 'this is a test'})
        with self.assertRaises(ValueError):
            g.job_arguments = '--bad_job_argument1'
        with self.assertRaises(ValueError):
            g.job_arguments = {'bad_job_argument2' : 'test'}
        with self.assertRaises(ValueError):
            g.job_arguments = {"--JOB_NAME" : "new_job_name"}

    def test_db_value_properties(self) :
        g = GlueJob('example/glue_jobs/simple_etl_job/', bucket = 'alpha-everyone', job_role = 'alpha_user_isichei', job_arguments={'--test_arg': 'this is a test'})

        g.job_name = 'changed_job_name'
        self.assertEqual(g.job_name, 'changed_job_name')

        g.bucket = "new-bucket"
        self.assertEqual(g.bucket, "new-bucket")
        with self.assertRaises(ValueError):
            g.bucket = "s3://new-bucket"

        g.job_role = 'alpha_new_user'
        self.assertEqual(g.job_role, 'alpha_new_user')

        g.job_arguments = {"--new_args" : "something"}
        self.assertEqual(g.job_arguments["--new_args"], "something")

class TableTest(unittest.TestCase):

    def test_table_init(self):
        tm = read_table_json("example/meta_data/db1/teams.json")

        self.assertTrue(tm.database is None)

        gtd = tm.glue_table_definition("full_db_path")
        self.assertTrue(gtd["StorageDescriptor"]["Location"] == 'full_db_path/teams/')



class DatabaseMetaTest(unittest.TestCase):
    """
    Test the Databasse_Meta class
    """

    def test_init(self) :
        db = DatabaseMeta(name = 'workforce', bucket = 'my-bucket', base_folder = 'database/database1', description='Example database')
        self.assertEqual(db.name, 'workforce')
        self.assertEqual(db.description, 'Example database')
        self.assertEqual(db.bucket, 'my-bucket')
        self.assertEqual(db.base_folder, 'database/database1')

    def test_read_json(self) :
        db = read_database_folder('example/meta_data/db1/')
        self.assertEqual(db.name, 'workforce')
        self.assertEqual(db.description, 'Example database')
        self.assertEqual(db.bucket, 'my-bucket')
        self.assertEqual(db.base_folder, 'database/database1')

    def test_db_to_dict(self) :
        db = DatabaseMeta(name = 'workforce', bucket = 'my-bucket', base_folder = 'database/database1', description='Example database')
        db_dict = read_json('example/meta_data/db1/database.json')
        self.assertDictEqual(db_dict, db.to_dict())

    def test_db_write_to_json(self) :
        db = DatabaseMeta(name = 'workforce', bucket = 'my-bucket', base_folder = 'database/database1', description='Example database')
        t = TableMeta(name = 'table1', location = 'somewhere')
        db.add_table(t)

        with tempfile.TemporaryDirectory() as tmpdirname:
            db.write_to_json(tmpdirname)
            dbr = read_json(os.path.join(tmpdirname, 'database.json'))
            tr = read_json(os.path.join(tmpdirname, 'table1.json'))
        
        self.assertDictEqual(dbr, db.to_dict())
        self.assertDictEqual(tr, t.to_dict())

        with tempfile.TemporaryDirectory() as tmpdirname:
            db.write_to_json(tmpdirname, write_tables=False)

            dbr = read_json(os.path.join(tmpdirname, 'database.json'))
            self.assertDictEqual(dbr, db.to_dict())

            # Check that only db has been written
            with self.assertRaises(FileNotFoundError) : 
                tr = read_json(os.path.join(tmpdirname, 'table1.json'))

    def test_db_value_properties(self) :
        db = read_database_folder('example/meta_data/db1/')
        db.name = 'new_name'
        self.assertEqual(db.name,'new_name')
        db.description = 'new description'
        self.assertEqual(db.description,'new description')
        db.bucket = 'new-bucket'
        self.assertEqual(db.bucket, 'new-bucket')
        db.base_folder = 'new/folder/location'
        self.assertEqual(db.base_folder, 'new/folder/location')

    def test_table_to_dict(self) :
        db = read_database_folder('example/meta_data/db1/')
        test_dict = read_json('example/meta_data/db1/teams.json')
        self.assertDictEqual(test_dict, db.table('teams').to_dict())

    def test_db_table_names(self) :
        db = read_database_folder('example/meta_data/db1/')
        t = all(t in ['teams', 'employees', 'pay'] for t in db.table_names)
        self.assertTrue(t)

    def test_db_name_validation(self) :
        db = read_database_folder('example/meta_data/db1/')
        with self.assertRaises(ValueError) : 
            db.name = 'bad-name'

    def test_db_glue_name(self) :
        db = read_database_folder('example/meta_data/db1/')
        self.assertEqual(db.name, 'workforce')

        db_dev = read_database_folder('example/meta_data/db1/')
        self.assertEqual(db_dev.name, 'workforce')

    def test_db_s3_database_path(self) :
        db = read_database_folder('example/meta_data/db1/')
        self.assertEqual(db.s3_database_path, 's3://my-bucket/database/database1')

    def test_db_table(self) :
        db = read_database_folder('example/meta_data/db1/')
        self.assertTrue(isinstance(db.table('employees'), TableMeta))
        self.assertRaises(ValueError, db.table, 'not_a_table_object')

    def test_glue_specific_table(self):
        t = read_table_json("example/meta_data/db1/pay.json")
        glue_def = t.glue_table_definition("db_path")
        self.assertTrue(t.glue_table_definition("db_path")["Parameters"]['skip.header.line.count'] == '1')

    def test_add_remove_table(self) :
        db = read_database_folder('example/meta_data/db1/')
        self.assertRaises(ValueError, db.remove_table, 'not_a_table')
        db.remove_table('employees')
        tns = db.table_names
        self.assertEqual(set(tns),set(['teams', 'pay']))

        emp_table = read_table_json('example/meta_data/db1/employees.json')
        db.add_table(emp_table)
        t = all(t in ['teams', 'employees', 'pay'] for t in db.table_names)
        self.assertTrue(t)

        self.assertRaises(ValueError, db.add_table, 'not a table obj')
        self.assertRaises(ValueError, db.add_table, emp_table)

    def test_location(self):
        db = read_database_folder('example/meta_data/db1/')
        tbl = db.table('teams')
        gtd = tbl.glue_table_definition()
        location = gtd["StorageDescriptor"]["Location"]
        self.assertTrue(location == 's3://my-bucket/database/database1/teams/')

    def test_glue_database_creation(self) :
        session = boto3.Session()
        credentials = session.get_credentials()
        has_access_key = True
        try :
            ac = credentials.access_key
        except :
            has_access_key = False

        if has_access_key :
            db = read_database_folder('example/meta_data/db1/')
            db_suffix = '_unit_test_'
            db.name = db.name + db_suffix
            db.create_glue_database()
            resp = _glue_client.get_tables(DatabaseName = db.name)
            test_created = all([r['Name'] in db.table_names for r in resp['TableList']])
            self.assertTrue(test_created, msg= "Note this requires user to have correct credentials to create a glue database")
            self.assertEqual(db.delete_glue_database(), 'database deleted')
            self.assertEqual(db.delete_glue_database(), 'Cannot delete as database not found in glue catalogue')
        else :
            print("\n***\nCANNOT RUN THIS UNIT TEST AS DO NOT HAVE ACCESS TO AWS.\n***\nskipping ...")
            self.assertTrue(True)

class TableMetaTest(unittest.TestCase):
    """
    Test Table Meta class
    """
    def test_data_type_conversion_against_gluejobutils(self) :
        with urllib.request.urlopen("https://raw.githubusercontent.com/moj-analytical-services/gluejobutils/master/gluejobutils/data/data_type_conversion.json") as url:
            gluejobutils_data = json.loads(url.read().decode())
        self.assertDictEqual(_agnostic_to_glue_spark_dict, gluejobutils_data)

    def test_null_init(self) :
        tm = TableMeta('test_name', location = 'folder/')

        self.assertEqual(tm.name, 'test_name')
        self.assertEqual(tm.description, '')
        self.assertEqual(tm.data_format, 'csv')
        self.assertEqual(tm.location, 'folder/')
        self.assertEqual(tm.columns, [])
        self.assertEqual(tm.partitions, [])
        self.assertEqual(tm.glue_specific, {})


        kwargs = {
            "name": "employees",
            "description": "table containing employee information",
            "data_format": "parquet",
            "location": "employees/",
            "columns": [
            {
                "name": "employee_id",
                "type": "int",
                "description": "an ID for each employee"
            },
            {
                "name": "employee_name",
                "type": "character",
                "description": "name of the employee"
            },
            {
                "name": "employee_dob",
                "type": "date",
                "description": "date of birth for the employee"
            }]
        }

        tm2 = TableMeta(**kwargs)
        self.assertEqual(tm2.name, kwargs['name'])
        self.assertEqual(tm2.description, kwargs['description'])
        self.assertEqual(tm2.data_format, kwargs['data_format'])
        self.assertEqual(tm2.location, kwargs['location'])
        self.assertEqual(tm2.columns, kwargs["columns"])
        self.assertEqual(tm2.glue_specific, {})
        with self.assertRaises(ValueError) :
            tm2.database = 'not a database obj'
    
    def test_db_name_validation(self) :
        tm = TableMeta('test_name', location = 'folder/')
        with self.assertRaises(ValueError) :
            tm.name = 'bad-name'

    def test_column_operations(self) :
        kwargs = {
            "name": "employees",
            "description": "table containing employee information",
            "data_format": "parquet",
            "location": "employees/",
            "columns": [
            {
                "name": "employee_id",
                "type": "int",
                "description": "an ID for each employee"
            },
            {
                "name": "employee_name",
                "type": "character",
                "description": "name of the employee"
            }]
        }

        columns_test = [
            {
                "name": "employee_id2",
                "type": "character",
                "description": "a new description"
            },
            {
                "name": "employee_name",
                "type": "character",
                "description": "name of the employee"
            }]

        new_col = {
                "name": "employee_dob",
                "type": "date",
                "description": "date of birth for the employee"
            }

        tm = TableMeta(**kwargs)

        # Test add
        tm.add_column(**new_col)
        new_cols = kwargs["columns"] + [new_col]
        self.assertEqual(tm.columns, new_cols)

        # Test add failure
        with self.assertRaises(ValueError) :
            tm.add_column(name = "test:!@", type = 'something', description = '')

        # Test remove
        tm.remove_column("employee_dob")
        self.assertEqual(tm.columns, kwargs['columns'])

        # Test remove failure
        with self.assertRaises(ValueError) :
            tm.remove_column('j_cole')

        # Test update column failure
        tm.update_column('employee_id', new_name='employee_id2', new_type='character', new_description='a new description')
        self.assertEqual(tm.columns, columns_test)
        
        with self.assertRaises(ValueError) :
            tm.update_column('employee_id2')
        
        with self.assertRaises(ValueError) :
            tm.update_column('j_cole', new_type = 'int')

if __name__ == '__main__':
    unittest.main()
