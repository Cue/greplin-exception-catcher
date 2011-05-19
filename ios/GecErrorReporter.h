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

#import <Foundation/Foundation.h>

#define GEC_REPORT_ERROR(__exception__,__message__) [[GecErrorReporter sharedInstance] reportError:__exception__ andMessage:__message__];

@interface GecErrorReporter : NSObject {
    NSURL *serverAddress;
    NSString *secret;
    NSString *environment;
    NSString *project;
    
    NSInteger itemLimit;
}

+ (GecErrorReporter *)sharedInstance;

- (void)reportError:(NSException *)exception andMessage:(NSString *)message;

- (void)syncErrors;

@property (nonatomic, retain) NSURL* serverAddress;
@property (nonatomic, retain) NSString* secret;
@property (nonatomic, retain) NSString* environment;
@property (nonatomic, retain) NSString* project;
@property NSInteger itemLimit;

@end
