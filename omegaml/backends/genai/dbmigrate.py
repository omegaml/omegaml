from sqlalchemy import create_engine, Column, Integer, String, MetaData, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker


class DatabaseMigrator:
    """ A utility class for performing database schema migrations using SQLAlchemy.

    This class allows you to manage schema changes, such as adding or dropping columns,
    based on a given SQLAlchemy model. It can handle both direct SQL execution for
    schema modifications (e.g., `ALTER TABLE`) and ORM-based querying when using
    SQLAlchemy's session for transaction management.

    Attributes:
        model (Base): The SQLAlchemy model (Base class) representing the table to migrate.
        engine (Engine): The SQLAlchemy engine used for database connection (if URL is provided).
        session (Session): The SQLAlchemy session object used for executing transactions and queries.
        connection (Connection): The raw database connection object when directly provided.

    Methods:
        get_current_columns(table_name):
            Returns the current columns in the database for the given table.

        add_column(table_name, column_name, column_type):
            Adds a new column to the specified table in the database.

        drop_columns(table_name, columns_to_drop):
            Drops the specified columns from the table, creating a new table and transferring data.

        apply_migration():
            Compares the model's columns with the current database schema and applies necessary
            migrations (add, modify, or drop columns).

        run_migration():
            Runs the migration process by calling the `apply_migration` method.

    Example usage with a database URL:
        migrator = DatabaseMigrator(User, "sqlite:///example.db")
        migrator.run_migration()

    Example usage with an existing connection:
        engine = create_engine("sqlite:///example.db")
        Session = sessionmaker(bind=engine)
        session = Session()
        migrator = DatabaseMigrator(User, session)
        migrator.run_migration()
        session.close()

    Notes:
        * This class is designed to work with SQLAlchemy ORM models and requires the SQLAlchemy library.
        * created with the help of gpt-4o
    """

    def __init__(self, database_url_or_connection, model=None):
        self.model = model
        self.database_url_or_connection = database_url_or_connection

    def __call__(self, model):
        """Set the model for migration."""
        self.model = model
        return self

    def __enter__(self):
        """Context manager entry point."""
        database_url_or_connection = self.database_url_or_connection
        # If a string is provided, it's a database URL, so create an engine and session
        if isinstance(database_url_or_connection, str):
            self.engine = create_engine(database_url_or_connection)
            self.Session = sessionmaker(bind=self.engine)
            self.session = self.Session()
        else:
            self.engine = database_url_or_connection.engine if hasattr(database_url_or_connection,
                                                                       'engine') else database_url_or_connection
            self.Session = sessionmaker(bind=self.engine)
            self.session = self.Session()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit point."""
        if getattr(self, 'session', None):
            self.session.close()
        if getattr(self, 'engine'):
            self.engine.dispose()

    def get_current_columns(self, table_name):
        """Get current columns in the database for a given table."""
        self.model.metadata.create_all(bind=self.session.bind)
        metadata = MetaData()
        metadata.reflect(bind=self.session.bind, only=[table_name])
        table = metadata.tables[table_name]
        return {column.name: column.type for column in table.columns}

    def add_column(self, table_name, column_name, column_type):
        """Add a new column to the table."""
        print(f"Adding column: {column_name} to {table_name}")
        self.session.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type.compile()}'))

    def drop_columns(self, table_name, columns_to_drop):
        """Drop specified columns from the table."""
        print(f"Dropping columns: {columns_to_drop} from {table_name}")
        new_table_name = f"{table_name}_new"
        new_columns = [column for column in self.model.__table__.columns if column.name not in columns_to_drop]

        # Create new table
        self.session.execute(
            text(
                f'CREATE TABLE {new_table_name} ({", ".join([f"{col.name} {col.type.compile()}" for col in new_columns])})'))

        # Copy data from the old table to the new table
        columns_to_copy = ', '.join([col.name for col in new_columns])
        self.session.execute(
            text(f'INSERT INTO {new_table_name} ({columns_to_copy}) SELECT {columns_to_copy} FROM {table_name}'))

        # Drop the old table
        self.session.execute(text(f'DROP TABLE {table_name}'))

        # Rename the new table to the original table name
        self.session.execute(text(f'ALTER TABLE {new_table_name} RENAME TO {table_name}'))

    def apply_migration(self):
        """Apply migration based on the model."""
        table_name = self.model.__tablename__
        current_columns = self.get_current_columns(table_name)
        model_columns = {column.name: column.type for column in self.model.__table__.columns}
        dialect = self.engine.dialect
        # Begin a transaction
        try:
            # Determine columns to add or modify
            for column_name, column_type in model_columns.items():
                current_column_type_str = current_columns[column_name].compile(dialect)
                column_type_str = column_type.compile(dialect)
                if column_name not in current_columns:
                    self.add_column(table_name, column_name, column_type)
                elif current_column_type_str != column_type_str:
                    print(
                        f"Altering column: {column_name} in {table_name} from {current_column_type_str} to {column_type_str}")
                    # Note: Altering column types can be complex and may require additional handling
                    self.session.execute(
                        text(
                            f'ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE {column_type_str}'))

            # Determine columns to drop
            columns_to_drop = [column_name for column_name in current_columns if column_name not in model_columns]
            if columns_to_drop:
                self.drop_columns(table_name, columns_to_drop)

            # Commit the transaction
            self.session.commit()

        except Exception as e:
            # Rollback if something goes wrong
            print(f"Migration failed: {e}")
            self.session.rollback()
            raise

    def run_migrations(self, models):
        for model in models:
            with self(model):
                self.apply_migration()


def test():
    # Example SQLAlchemy model

    def initial_table():
        Base = declarative_base()

        class User(Base):
            __tablename__ = 'users'
            id = Column(Integer, primary_key=True)
            name = Column(String)
            age = Column(Integer)

        return User

    def new_table():
        Base = declarative_base()

        class User(Base):
            __tablename__ = 'users'
            id = Column(Integer, primary_key=True)
            name = Column(String)
            age = Column(Integer)
            email = Column(String)

        return User

    # Using a connection object instead of a URL
    engine = create_engine("sqlite:///example.db")
    connection = engine.connect()
    migrator = DatabaseMigrator(connection)
    with migrator(initial_table()) as m:
        m.run_migration()
        print(migrator.get_current_columns('users'))
    with migrator(new_table()) as migrator:
        migrator.run_migration()
        print(migrator.get_current_columns('users'))
    connection.close()


# Example usage with a connection
if __name__ == "__main__":
    test()
