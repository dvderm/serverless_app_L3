from aws_cdk import (
    RemovalPolicy,
    CfnOutput,
    Duration,
    aws_dynamodb as dynamodb,
    Stack,
    aws_lambda as lambda_,
    aws_cloudwatch as cloudwatch
)
from constructs import Construct
from aws_solutions_constructs.aws_lambda_dynamodb import LambdaToDynamoDB

class ServerlessAppStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        products_table = dynamodb.Table(self, 'ProductsTable',                                      # Eerste twee parameters zijn scope (self) en id (ProductsTable) wat feitelijk de naam van de construct is
                                        partition_key=dynamodb.Attribute(
                                            name='id',
                                            type=dynamodb.AttributeType.STRING
                                        ),
                                        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                                        removal_policy=RemovalPolicy.DESTROY)
        
        product_list_function = lambda_.Function(self, 'ProductListFunction',                       # Documentatie over deze functie: https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html
                                                 code=lambda_.Code.from_asset('lambda_src'),        # Code is een class van aws_lambda package waarbij je de from_asset() method hebt die je het pad kunt geven van de directory waarin je Lambda Function code zit
                                                 handler='product_list_function.lambda_handler',    # Wanneer je een python script in een file zet, wordt het een module in Python. module: product_list_function, method: lambda_handler. handler is the name of the method executed when you trigger this lambda function
                                                 runtime=lambda_.Runtime.PYTHON_3_10,
                                                 environment={
                                                     'TABLE_NAME': products_table.table_name        # De lambda_handler-method heeft een TABLE_NAME nodig dus die wordt hier gedefinieerd
                                                 })
        
        # Granting permissions to the Lambda Function to read data from the DynamoDB table
        products_table.grant_read_data(product_list_function.role)                                  # grant_read_data method. Grantee should be the product_list_function IAM role. the .role attribute returns its IAM service role. Commenting this out will trigger the alarm that has been set with the errors_metric.create_alarm() method
        
        # Adding a Lambda URL to the Lambda function to execute it from the internet
        product_list_url = product_list_function.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE) # add_function_url method. auth_type parameter. FunctionUrlAuthType.NONE enumeration. 

        # Adding a stack output for the function URL to access the URL more easily than having to open the lambda function in AWS GUI and finding the URL there
        CfnOutput(self, 'ProductListUrl',                                                           # Defined in our stack so its scope will be "self". 
                  value=product_list_url.url)                                                       # url attribute van de product_list_url variable om de URL te krijgen. 
        
        # Configuring an alarm for the Lambda function's error metric (if the Lambda fails, CloudWatch alarm will go off)
        errors_metric = product_list_function.metric_errors( # metric_errors() method which will return the metric for the lambda function's errors.
            label='ProductListFunction Errors', # label parameter: label for the metric that will be displayed on graphs
            period=Duration.minutes(5), # period parameter. Duration class from the core package provides methods for periods like seconds, minutes, hours, etc. Minutes method was used in this case and 5 was given to the method's only parameter.
            statistic=cloudwatch.Stats.SUM # statistic parameter. Using cloudwatch "Stats"-enumeration class and its member for the SUM
        )

        errors_metric.create_alarm(self, 'ProductListErrorsAlarm', # create_alarm() method. Scope will be "self" as in all constructs in the stack. 
                                   evaluation_periods=1, # evaluate the threshold for a single period
                                   threshold=1, # Single errors within one evaluation period of 5 minutes become sufficient to compare
                                   comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD, #cloudwatch package's ComparisonOperator enumeration class, GREATE_THAN_OR_EQUAL_TO_THRESHOLD-constant to trigger the alarm if the threshold is reached or exceeded.
                                    treat_missing_data=cloudwatch.TreatMissingData.IGNORE # Don't trigger an alarm if the URL is not accessed within the alarm period
                                   ) 