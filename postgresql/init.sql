-- Create function_logs table for OpenFaaS function invocation logging
CREATE TABLE IF NOT EXISTS function_logs (
    id SERIAL PRIMARY KEY,
    function_name VARCHAR(100) NOT NULL,
    invocation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    request_data JSONB,
    response_data JSONB,
    status VARCHAR(50),
    duration_ms INTEGER,
    error_message TEXT
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_function_logs_time ON function_logs(invocation_time DESC);
CREATE INDEX IF NOT EXISTS idx_function_logs_name ON function_logs(function_name);
CREATE INDEX IF NOT EXISTS idx_function_logs_status ON function_logs(status);

-- Grant permissions to openfaas_user
GRANT ALL PRIVILEGES ON TABLE function_logs TO openfaas_user;
GRANT USAGE, SELECT ON SEQUENCE function_logs_id_seq TO openfaas_user;
