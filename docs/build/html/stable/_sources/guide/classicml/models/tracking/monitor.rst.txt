Understanding Drift Monitoring
==============================

omega-ml implements drift monitoring by taking snapshots of data and comparing them to a baseline snapshot.
Each snapshot is a statistical summary of the data. The comparison is done using a statistical test that
compares the two snapshots. The result of the test is a drift score that indicates the degree of change. The
drift score is then used to generate a report that shows the changes in the data. The score can be plotted
over time to show trends, and individual features can be examined to see which features are changing and how.





