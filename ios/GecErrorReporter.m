/*
 * Copyright 2011 The greplin-exception-catcher Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#import "GecErrorReporter.h"
#import "JSON.h" // From http://stig.github.com/json-framework/

static GecErrorReporter *sharedInstance = nil;


@interface UploadDelegate : NSObject

- (void)connectionDidFinishLoading:(NSURLConnection *)connection;
    
@end


@implementation GecErrorReporter

@synthesize serverAddress;
@synthesize secret;
@synthesize environment;
@synthesize project;

+ (GecErrorReporter *)sharedInstance {
    if (sharedInstance == nil) {
        sharedInstance = [[[GecErrorReporter alloc] init] retain];
    }
    return sharedInstance;
}

+ (NSString *)crashFilePath {
    NSArray * paths = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES);
    return [[paths objectAtIndex:0] stringByAppendingString:@"/crash.gec"];
}

- (void)reportError:(NSException *)exception andMessage:(NSString *)message {
    NSMutableDictionary *result = [NSMutableDictionary dictionaryWithCapacity:7];
    [result setObject:project forKey:@"project"];
    [result setObject:environment forKey:@"environment"];
    [result setObject:[UIDevice currentDevice].model forKey:@"serverName"];
    [result setObject:[exception name] forKey:@"type"];
    [result setObject:[exception reason] forKey:@"message"];
    [result setObject:message forKey:@"logMessage"];
    [result setObject:[NSNumber numberWithInt:(int)[[NSDate date] timeIntervalSince1970]] forKey:@"timestamp"];
    
    [result setObject:[[exception callStackSymbols] componentsJoinedByString:@"\n"] forKey:@"backtrace"];

    NSData *jsonData = [[result JSONRepresentation] dataUsingEncoding:NSUTF8StringEncoding];
    [jsonData writeToFile:[GecErrorReporter crashFilePath] atomically:YES];
}


- (void)uploadError {
    NSString *path = [@"report?key=" stringByAppendingString:secret];
    NSURL *url = [NSURL URLWithString:path relativeToURL:serverAddress];
    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
    [request setHTTPMethod:@"POST"];
    [request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
    [request setHTTPBody:[NSData dataWithContentsOfFile:[GecErrorReporter crashFilePath]]];
    
    [NSURLConnection connectionWithRequest:request delegate:[[[UploadDelegate alloc] init] autorelease]];
}

- (void)syncErrors {
    if ([[NSFileManager defaultManager] fileExistsAtPath:[GecErrorReporter crashFilePath]]) {
        [self uploadError];
    }
}

- (void)deleteCrashFile {
    [[NSFileManager defaultManager] removeItemAtPath:[GecErrorReporter crashFilePath] error:nil];   
}

- (void)dealloc {
    [super dealloc];
    [serverAddress release];
    [secret release];
    [environment release];
    [project release];
}

@end


@implementation UploadDelegate

- (void)connectionDidFinishLoading:(NSURLConnection *)connection {
    [[GecErrorReporter sharedInstance] deleteCrashFile];
}

- (void)connection:(NSURLConnection *)connection didFailWithError:(NSError *)error {
    NSLog(@"Failed to upload exception: %@", error);
}

@end
